# Contract implementation audit

This checklist records the implemented standard CHOAM Contract market and
completion system. The official summary in `docs/rules/choam-module.md` is the
rules source of truth; Dune Cards Hub is used only for printed tile identity and
visual reference.

## Implemented behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Manifest | The 20 standard Uprising Contracts have unique stable IDs, typed completion conditions and rewards, and Dune Cards Hub URLs. | The printed images were checked individually; Harvest 3+ uses the printed 3-Solari reward rather than DIU's incorrect value of 1. Corrected 2026-08-30: the set contains both Sardaukar tiles (Sardaukar II recalls one of your other Agents [Main p. 20]); the previously listed third High Council tile is a Rise of Ix jumpstart tile whose printed reward includes a Tech acquisition and does not belong to the standard 20. |
| Setup | With CHOAM enabled, one recorded chance permutation shuffles all 20 tiles, exposes the first two, and leaves 18 in the face-down bank. | With CHOAM disabled, no Contract chance decision or state is created. |
| Market choice | A Contract icon selects either face-up tile by stable instance ID. The bank's top tile refills the same market position. | The already-shuffled bank order stays authoritative and replayable; taking a tile adds no new chance outcome. |
| Depletion | Once the bank is empty, taking a face-up tile shrinks the market. Once the market is also empty, each remaining Contract icon grants 2 Solari. | A doubled Conflict reward can take the last tile and automatically convert its second icon. |
| Sources | Accept Contract and Conflict rewards use the same serial choice frame. | Module-off Accept Contract and Conflict rewards retain the existing 2-Solari replacement. |
| Completion snapshot | Agent placement snapshots every then-held matching space or Harvest Contract. | A Contract taken later in the same turn cannot complete retroactively. |
| Space completion | Every matching held Contract is mandatory and exposed as its own ordered Agent-turn effect. | Contract rewards can interleave with board-space and Agent-box effects; the frame cannot advance while a matching mandatory Contract remains. |
| Harvest | Maker-space visits track Spice gained from all sources during the turn, including Maker bonus and Agent-card effects. | Later Spice spending is added back to the gross-gain counter and cannot undo an already-met threshold. |
| Acquire | Acquiring The Spice Must Flow through Reveal or a supported Agent-card acquisition completes Acquire. | Existing card-acquisition triggers resolve before the Contract reward as the OQ-012 project convention for this non-conflicting standard tile. |
| Rewards | Resources, fixed Faction Influence, troops, personal-card draw, Spy placement, and another face-up Contract all use shared typed transitions. | Recruited Contract troops increase the same Combat deployment limit as troops recruited from other Agent-turn sources. |
| Immediate | Taking Immediate grants its typed 2-Solari reward and moves the tile directly to completed Contracts. | It never occupies the active zone. |
| Zones | The authoritative state keeps bank, face-up market, active player Contracts, and completed player Contracts disjoint. | Active Contract IDs and completed counts are observed; bank order and completed identities are redacted under OQ-010. |
| Gather Intelligence | Gather Intelligence's immediate window resolves before Contract completion actions. | Official relative ordering remains unanswered under OQ-011; this is an explicit tested project convention. |
| Action codec | `take_contract` and `complete_contract` have one actor-neutral template per standard Contract; Contract Spy placement/recall uses post-ID templates. | Codec v58 keeps the base catalog at 3,377; CHOAM Imperium destinations and choices expand the module catalog to 3,598. |

## Deferred boundaries

- Shaddam Corrino IV's set-aside Sardaukar Contract alternative.
- An official answer for Gather Intelligence versus Contract completion under
  OQ-011; the implemented project convention remains clearly labeled until then.
- Completed Contract identity visibility under OQ-010.

## Verification

- Main Rulebook p. 16 and the pinned FAQ were revalidated from the official
  online resources on 2026-08-27.
- All 20 conditions and rewards were cross-checked against their linked Dune
  Cards Hub images on 2026-08-28. The official Main and FAQ determine timing
  and mandatory/order rules; Dune Cards Hub is used only to read tile print.
- The standard-set membership was re-verified on 2026-08-30: the six-player
  supplement's base-CHOAM setup sets aside "the two Sardaukar contracts"
  before shuffling, so both Sardaukar tiles belong to the shuffled 20, and the
  composition (Acquire 1, Arrakeen 2, Deliver Supplies 1, Espionage 2,
  Harvest 3+ 2, Harvest 4+ 2, Heighliner 3, High Council 2, Immediate 1,
  Research Station 2, Sardaukar 2) sums to exactly 20. The catalog-497 "High
  Council" tile prints a Rise of Ix Tech-acquisition reward and is a RoI
  jumpstart tile; DIU's flat contract list had dropped that Tech icon, which
  is how it was originally mistaken for a standard tile.
- Setup replay, take/refill, partial and complete depletion, Immediate,
  board-space/Harvest/Acquire completion, all reward shapes, same-space multiple
  Contracts, no retroactive completion, Gather ordering, troop deployment,
  observation redaction, deterministic action replay, and codec round trips have
  regression tests.
