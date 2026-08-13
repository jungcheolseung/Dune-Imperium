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
