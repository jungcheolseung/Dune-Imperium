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
- DIU's `shieldwall` boolean denotes the crossed Shield Wall detonation icon on
  a Conflict card. The local field is named `shield_wall_detonation` to avoid
  confusing it with the current board token state.
