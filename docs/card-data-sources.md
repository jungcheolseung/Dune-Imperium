# Card data transcription sources

Card identities and effects remain part of this repository's typed content
manifests. External repositories are development references, not runtime data
dependencies or rules authorities.

## DIU reference dataset

- Repository: <https://github.com/valrvrt/DIU>
- Reviewed commit: `990523441421d34a670505d5b32318f01754b960`
- Useful files: `data/conflicts.JSON`, `data/imperium.JSON`,
  `data/intrigue.JSON`, `data/contracts.JSON`, and `data/leader_data/*.json`

The DIU JSON is useful for bootstrapping card-effect transcription. Values are
normalized into this project's stable IDs and typed schemas rather than copied
or loaded at runtime. DIU does not provide a root README or license at the
reviewed commit, and its data contains known spelling and schema inconsistencies.
It therefore cannot establish rules provenance or replace validation.

Dire Wolf Digital's official rules and FAQ remain authoritative for rules
adjudication. Dune Cards Hub remains the card-level fallback when a DIU value is
missing, ambiguous, or conflicts with already verified content.

### Development audit workflow

DIU is never discovered or loaded by the game runtime. A developer may pass an
explicit working-copy path to the read-only audit command:

```bash
uv run dune-imperium-audit-diu ../DIU/data/imperium.JSON
```

The audit performs the following normalization without writing generated data:

- matches DIU names to the project's stable card IDs, including the recorded
  `Branching Paths` / `Branching Path` spelling alias;
- distinguishes the seven starting-card, two Reserve, and 54 shared Imperium
  identities;
- converts `agent_icon` / `agent_icons`, scalar/list icon values, and the three
  color icons to the local `AgentIcon` values;
- converts `faction` / `factions` and display/lower-case spellings to local
  Faction values;
- recursively inventories every `type` under Agent, Reveal, Fremen Bond,
  acquire, discard, and trash effect containers;
- rejects missing or duplicate identities, unknown icons and Factions, invalid
  container types, and group mismatches rather than guessing.

At the reviewed commit, all 63 identities match: seven starting cards, two
Reserve cards, and 54 shared Imperium cards. The recursive inventory contains
312 typed effect objects. DIU's declared quantity differs from the verified
local manifest for 48 identities, so the audit reports but never imports source
quantities. The local manifest remains authoritative for physical counts and
CHOAM inclusion.

The normalized audit result is an input to later typed transcription work, not
a generated runtime manifest. A card effect enters production only when it is
represented by local typed content, covered by tests, and checked against card
art or an applicable official clarification where DIU is ambiguous.

### DIU-first Imperium batches

The first shared-deck batch transcribes Maula Pistol and Truthtrance. Both use
only effect shapes already supported by the local rules engine: static Agent
icons, static Reveal Persuasion or strength, and a replayable personal-card
draw. DIU supplies the initial Faction, icon, and effect transcription. The
local manifest remains authoritative for stable IDs, acquisition costs,
physical quantities, CHOAM inclusion, and catalog URLs.

The second batch transcribes Sardaukar Soldier. Its static Emperor affiliation,
City icon, and Reveal values reuse the personal-card resolver, while its
on-trash Intrigue draw adds a typed trash trigger. Agent-card and Combat-reward
trash now share that transition, including the existing rule that a trashed
Reserve card returns to its stack.

The third batch transcribes Hidden Missive. Its conditional Agent effect checks
Bene Gesserit Influence before adding one troop to the Agent turn's common
recruit-and-deploy count and drawing through the replayable personal-deck path.
The troop recruitment transition is shared with board-space effects.

The fourth batch transcribes Desert Survival. Its Agent box opens an explicit
decline-or-trash choice over the player's hand, discard pile, and cards in play.
The selected card resolves through the same trash transition used by Combat
rewards, so Reserve returns and on-trash triggers remain consistent.

The fifth batch transcribes Smuggler's Harvester. Its Agent bonus checks the
visited board space's typed Maker flag before awarding one Spice; non-Maker
Spice Trade destinations expose no card effect. Its Reveal value is static.

The sixth batch transcribes Fedaykin Stilltent and introduces typed automatic
Reveal gains for public resources and recruited troops. Its Agent effect shares
the Maker-space condition and troop-recruit transition, while its Reveal effect
adds one Water directly during Reveal setup.

The seventh batch transcribes Northern Watermaster. Its unconditional Agent
effect gains one Water, while its Reveal Spice requires another Fremen card
among the cards already in play or revealed in the same turn. Faction
affiliation is now uniform across every personal-card source schema so that
this bond check does not depend on card origin.

The eighth batch transcribes Maker Keeper. Its Bene Gesserit and Fremen
Influence thresholds are evaluated independently, awarding Water, Spice, or
both, while its dual affiliation, two Agent icons, and static Reveal Persuasion
use the common personal-card schema.

The ninth batch transcribes Southern Elders. Personal cards may now carry
multiple automatic Reveal effects, each with an optional typed Faction Bond.
The same shared bond check gates its Bene Gesserit Agent recruitment and Fremen
Reveal Persuasion without conflating the two affiliations.

The tenth batch transcribes Weirding Woman. Bene Gesserit Bond moves the Agent
card from play back into its owner's hand, allowing the same physical instance
to participate in the later Reveal turn while preserving zone uniqueness.

The eleventh batch transcribes Ecological Testing Station. Its Agent effect
opens an explicit decline-or-pay choice for two Water and draws two cards through
the replayable personal-deck path. Its Fremen Bond Reveal Water uses the shared
conditional Reveal-effect collection.

The twelfth batch transcribes Paracompass. Reveal effects may now require High
Council or High Council together with Swordmaster, allowing its two conditional
Persuasion gains to stack with the board's normal Council bonus. Its Agent
effect is an unconditional two-Solari gain.

The thirteenth batch transcribes Overthrow and opens the typed acquisition-bonus
boundary. Its acquisition Intrigue draw resolves immediately, while cards whose
recorded acquisition bonus remains untyped are still filtered from engine legal
actions. Its Agent and Reveal effects reuse Influence and troop transitions.

Subsequent batches complete the non-CHOAM deck through Subversive Advisor and
codec version 55. The
authoritative card-by-card behavior and verification notes are maintained in
[the personal-card implementation audit](implementation-audits/personal-cards.md)
instead of duplicating every batch here. As of 2026-08-28, all 50 non-CHOAM and
four CHOAM-only Imperium identities have complete play data. The CHOAM batch
adds Contract-count Reveal scaling, Contract-market acquisition and Agent
effects, and qualifying self-trash choices. A card is hidden from playable
Agent paths until its full local transcription and regression tests are ready.

### Recorded discrepancies

- DIU records the standard Harvest 3+ Contract's reward as one Solari. The
  linked printed tile clearly shows three Solari, so the local typed Contract
  reward and regression test use three.
- DIU gives Smuggler's Haven one Solari as its unconditional Reveal resource.
  The printed card instead gives one Persuasion, followed by two Spice only
  while spying on a Maker board space, so the local transcription follows the
  verified card image.
- DIU gives Delivery Agreement one Reveal Persuasion and represents its
  qualifying trash branch as Spice. The printed card instead gives one Spice,
  or with at least four completed Contracts allows trashing itself for one
  Victory Point, so the local typed choice follows the image.
- DIU gives Priority Contracts two Reveal Persuasion. The printed card instead
  gives two Spice, or with at least four completed Contracts allows trashing
  itself for one Victory Point, so the local typed choice follows the image.
- DIU models Trade Dispute's trash icon with `deck: ["hand", "played"]`.
  The general Uprising trash rule also permits a card in the player's discard
  pile, and the black trash icon is optional. The local typed reward therefore
  follows the official general rule rather than DIU's zone list.
- DIU records Propaganda's battle icon as `unknown`; the printed question-mark
  icon is retained locally as the Endgame wild battle icon. Its first reward is
  also modeled as choosing two distinct Factions, not two unrestricted repeats.
- DIU represents Battle for Arrakeen's two-Spy arrow cost as a generic Spy
  resource cost. The printed upward arrows require recalling two placed Spies,
  so the local schema records a recall cost.
- DIU's `shieldwall` boolean denotes the crossed Shield Wall protection icon at
  the lower right of a Conflict card, not the detonation effect icon available
  on cards and Sietch Tabr. The local field is named `shield_wall_protected` and
  Siege of Arrakeen is corrected to `True` from its printed card image.

### Intrigue batches

Intrigue effects are transcribed into the composable effect DSL rather than
per-card enum members. DIU's `intrigue.JSON` (41 identities) supplies the
initial condition/cost/reward shape; each card is then checked against the
Dune Cards Hub card image (`https://dunecardshub.com/images/uprising-intrigue-<slug>.webp`),
which is fetched for review only and never stored in the repository.

The first batch transcribes Contingency Plan, Councilor's Ambition, Depart for
Arrakis, Intelligence Report, Market Opportunity, Mercenaries, Shaddam's Favor
and Strategic Stockpiling. DIU models Shaddam's Favor's unconditional troop as
a bare effect outside the Plot action and Contingency Plan as a required
choice; both are normalised into DSL options and sections locally.

The second batch transcribes Buy Access, Change Allegiances, Imperium
Politics, Opportunism, Sietch Ritual and Backed by CHOAM through DSL choice
slots. Two DIU values disagree with the printed cards and were corrected from
the card images: Imperium Politics offers Emperor or Spacing Guild Influence
(not Spacing Guild/Bene Gesserit), and Backed by CHOAM's Combat half needs two
completed Contracts (not four).

The third batch transcribes Detonation and Unexpected Allies from their card
images. DIU models Detonation's detonation half as `shield_active: false`
and Unexpected Allies as a sandworm plus `shield_active: false`; locally the
detonation icon is a detonate-or-keep choice because the rules make removing
the token optional [Main pp. 10, 20].

