# Contract implementation audit

This checklist records the implemented CHOAM Contract market and the completion
work that remains. The official summary in `docs/rules/choam-module.md` is the
rules source of truth; Dune Cards Hub is used only for printed tile identity and
visual reference.

## Implemented behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Manifest | The 20 standard Uprising Contracts have unique stable IDs and Dune Cards Hub URLs. | The 10 contrasting-back Rise of Ix Contracts are not part of the Uprising-only setup. |
| Setup | With CHOAM enabled, one recorded chance permutation shuffles all 20 tiles, exposes the first two, and leaves 18 in the face-down bank. | With CHOAM disabled, no Contract chance decision or state is created. |
| Market choice | A Contract icon selects either face-up tile by stable instance ID. The bank's top tile refills the same market position. | The already-shuffled bank order stays authoritative and replayable; taking a tile adds no new chance outcome. |
| Depletion | Once the bank is empty, taking a face-up tile shrinks the market. Once the market is also empty, each remaining Contract icon grants 2 Solari. | A doubled Conflict reward can take the last tile and automatically convert its second icon. |
| Sources | Accept Contract and Conflict rewards use the same serial choice frame. | Module-off Accept Contract and Conflict rewards retain the existing 2-Solari replacement. |
| Immediate | Taking Immediate grants 2 Solari and moves the tile directly to completed Contracts. | This is the only completion reward included in the market slice because leaving Immediate active would create an illegal intermediate state. |
| Zones | The authoritative state keeps bank, face-up market, active player Contracts, and completed player Contracts disjoint. | Active Contract IDs and completed counts are observed; bank order and completed identities are redacted under OQ-010. |
| Action codec | `take_contract(instance_id=...)` has one actor-neutral template per standard Contract in codec v56. | The base catalog stays at 3,377; the CHOAM catalog is 3,445 after its existing module-only card templates and 20 Contract choices. |

## Deferred completion systems

- Board-space, Harvest, and Acquire The Spice Must Flow completion triggers.
- The printed reward schema and every non-Immediate reward transition.
- Mandatory simultaneous completion of all matching Contracts and the FAQ's
  freely chosen ordering among Contract, board-space, and Agent-box effects.
- Shaddam Corrino IV's set-aside Sardaukar Contract alternative.
- Gather Intelligence versus Contract completion ordering under OQ-011.

## Verification

- Main Rulebook p. 16 and the pinned FAQ were revalidated from the official
  online resources on 2026-08-27.
- The 20 manifest identities were cross-checked against the Dune Cards Hub
  catalog, and Immediate's printed 2-Solari reward was visually checked there
  on 2026-08-27.
- Setup replay, take/refill, partial and complete depletion, Immediate,
  observation redaction, board-space and Conflict integration, and codec
  round-trip behavior have regression tests.
