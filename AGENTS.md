# Repository instructions

Read `README.md` before making architectural or rules-related changes.

## Rule sources

- The implementation target is the four-player base game of Dune: Imperium -
  Uprising.
- Prefer Dire Wolf Digital's official online resources:
  - https://www.direwolfdigital.com/dune-imperium/resources/
  - https://www.direwolfdigital.com/dune-imperium/resources/diu_rules
- Files under `rulebooks/` are the user's local reading copies. Do not load,
  extract, summarize, modify, or delete those PDFs by default.
- Read a local PDF only when the user explicitly requests it or when the official
  source is unavailable and the task cannot otherwise proceed.
- Retrieve only the sections needed for the current rule question. Record
  ambiguous interpretations in project documentation and protect chosen rulings
  with tests.
- Use `scripts/prepare_official_rules.py` when page-indexed text from an official
  PDF is needed. Keep its generated PDFs and text outside the repository. Update
  `scripts/official-rule-sources.json` and `docs/rules/sources.md` together when
  an official file version or checksum changes.
- Before implementing a rule, consult `docs/rules/README.md` and its cited source.
  Do not silently fill a gap in the official documents. Add it to
  `docs/rules/open-questions.md`, and clearly distinguish any later project
  convention from an official rule.
- When an official rule, FAQ ruling, or card transcription changes, update its
  source citation and relevant regression test in the same work unit.

## Card and image sources

- Use https://dunecardshub.com/uprising to find Uprising leader, deck, contract,
  and other card images or card-level reference data.
- Use https://dunecardshub.com and select another expansion when that expansion's
  card material is needed.
- Treat Dune Cards Hub as a card and visual reference, not as the authority for
  rules adjudication. Official Dire Wolf Digital rules and supplements take
  precedence when sources conflict.
- Before adding or redistributing image files in the project, verify the needed
  scope and applicable usage terms.
