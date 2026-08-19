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

Cards with trash triggers, restricted Spy placement, choices, conditions, or
new effect primitives are held for later batches even when their basic Reveal
values would otherwise be simple. This prevents a partially implemented card
from being exposed as fully playable.

### Recorded discrepancies

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
