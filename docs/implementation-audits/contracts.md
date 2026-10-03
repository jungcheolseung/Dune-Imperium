# Contract implementation audit

This checklist records the implemented standard CHOAM Contract market and
completion system. The official summary in `docs/rules/choam-module.md` is the
rules source of truth; Dune Cards Hub is used only for printed tile identity and
visual reference.

## Implemented behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Manifest | The 20 standard Uprising Contracts (18 printed faces: Espionage I and Harvest 3+ have two copies, the second as `<id>_copy_2` with `copy_of`) have unique stable IDs, typed completion conditions and rewards, and Dune Cards Hub URLs. | Corrected 2026-09-27: four Rise of Ix tiles (Espionage II, Harvest 3+ and 4+ with a Contract, Heighliner III) had stood in for Spice Refinery I and II and the two second copies; the membership now follows the BGG card inventory's Rise of Ix column and copy counts, which match the rulebook's 20 + 10 split and its "jumpstart" purpose (every Rise of Ix tile prints "+1 Contract") [Main p. 16] (see Verification). The printed images were checked individually; Harvest 3+ uses the printed 3-Solari reward rather than DIU's incorrect value of 1. Corrected 2026-08-30: the set contains both Sardaukar tiles (Sardaukar II recalls one of your other Agents [Main p. 20]); the previously listed third High Council tile is a Rise of Ix jumpstart tile whose printed reward includes a Tech acquisition and does not belong to the standard 20. |
| Setup | With CHOAM enabled, one recorded chance permutation shuffles all 20 tiles, exposes the first two, and leaves 18 in the face-down bank. | With CHOAM disabled, no Contract chance decision or state is created. |
| Market choice | A Contract icon selects either face-up tile by stable instance ID. The bank's top tile refills the same market position. | The already-shuffled bank order stays authoritative and replayable; taking a tile adds no new chance outcome. |
| Depletion | Once the bank is empty, taking a face-up tile shrinks the market. Once the market is also empty, each remaining Contract icon grants 2 Solari. | A doubled Conflict reward can take the last tile and automatically convert its second icon. |
| Sources | Accept Contract and Conflict rewards use the same serial choice frame. | Module-off Accept Contract and Conflict rewards retain the existing 2-Solari replacement. |
| Completion snapshot | Agent placement snapshots every then-held matching space or Harvest Contract. | A Contract taken later in the same turn cannot complete retroactively. |
| Space completion | Every matching held Contract is mandatory and exposed as its own ordered Agent-turn effect. | Contract rewards can interleave with board-space and Agent-box effects; the frame cannot advance while a matching mandatory Contract remains. |
| Harvest | Maker-space visits track Spice gained from all sources during the turn, including Maker bonus and Agent-card effects. | Later Spice spending is added back to the gross-gain counter and cannot undo an already-met threshold. |
| Acquire | Acquiring The Spice Must Flow through Reveal or a supported Agent-card acquisition completes Acquire. | Existing card-acquisition triggers resolve before the Contract reward as the OQ-012 project convention for this non-conflicting standard tile. |
| Rewards | Resources, fixed Faction Influence, troops, personal-card draw, Spy placement, and another face-up Contract all use shared typed transitions. | Recruited Contract troops increase the same Combat deployment limit as troops recruited from other Agent-turn sources. A Spy reward is mandatory while a Spy is in supply; with the supply empty it offers `decline_contract_spy` beside `recall_spy_for_contract`, "you may first recall" [Main pp. 11, 20] (OQ-057 (14); corrected 2026-09-26, the recall used to be forced). Sardaukar II's Recall Agent never takes the Agent sent this turn [Main p. 20], also when CHOAM Demands completes the tile (corrected 2026-09-26). An earlier turn's Into the Fray Agent in the Conflict (Duncan Idaho, Bloodlines) is one of "your Agents" too and may also be recalled -- never one sent this turn -- so the reward no longer fizzles when it is the only other Agent (2026-09-26 user ruling, OQ-068). With no other Agent at all the reward still fizzles (the designer's Sardaukar II ruling), but no longer unasked: the recall window always opens and then offers only `resolve_contract_without_recall`, which emits `contract_recall_unavailable`, while the page greys the recall out (user ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을 연다"; implemented 2026-10-02, OQ-068). |
| Immediate | Taking Immediate grants its typed 2-Solari reward and moves the tile directly to completed Contracts. | It never occupies the active zone. |
| Zones | The authoritative state keeps bank, face-up market, active player Contracts, and completed player Contracts disjoint. | Active and completed Contract IDs are observed by every seat (OQ-010 ruling 2, 2026-09-02: a completed Contract was face up and its completion announced); only the bank order is redacted. |
| Gather Intelligence | Gather Intelligence's immediate window resolves before Contract completion actions. | Official relative ordering remains unanswered under OQ-011; this is an explicit tested project convention. |
| Action codec | `take_contract` and `complete_contract` have one actor-neutral template per standard Contract; Contract Spy placement/recall uses post-ID templates. | Codec v58 keeps the base catalog at 3,377; CHOAM Imperium destinations and choices expand the module catalog to 3,598. |
| Bloodlines tokens | With `bloodlines` and the CHOAM Module the eight Bloodlines contract tokens (one copy each) shuffle into the same bank: Deliver Supplies, Earn Any Alliance, Harvest 3+, Harvest 4+, High Council, Immediate ("Requires an Intrigue card"), Secrets, Spice Refinery. Two new condition kinds (`earn_alliance`, `immediate_intrigue_trash`) and two reward fields (`intrigue_cards`, `deep_cover_spies`). | Transcribed from the card faces on 2026-09-09 and cross-checked against the BGG card inventory; details in the [Bloodlines audit](bloodlines.md) and [rules/bloodlines.md](../rules/bloodlines.md) section 1 [Bloodlines p. 2]. Earn Any Alliance completes through a post-step hook on the step's Alliance events (no Agent-visit snapshot; OQ-056), the new Immediate cannot be taken without a hand Intrigue card, waits in the active zone only while the `contract_intrigue_trash` frame is open, and completes when the card is trashed. |

## Deferred boundaries

- Set-aside access after market exhaustion is decided under OQ-021: while a
  set-aside tile remains, Shaddam's icon must take one, because the two-Solari
  reversion needs every Contract taken [Main p. 16] (user ruling 2026-10-04,
  codec v130; see the [Leader audit](leaders.md)); it reopens only on an
  official ruling.
- An official answer for Gather Intelligence versus Contract completion under
  OQ-011; the implemented project convention remains clearly labeled until then.

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
- **That 2026-08-30 composition was wrong** (user report 2026-09-27): "sums to
  exactly 20" was the only check, and four of the counted tiles were Rise of
  Ix jumpstart tiles. The BGG card inventory's Contracts tab marks the ten
  "Rise of Ix -Specific?" tiles -- Dreadnought, Espionage (1 Solari,
  Contract), Harvest 3+ (Contract), Harvest 4+ (2 Solari, Contract),
  Heighliner (3 Solari, Contract), High Council (the Rise of Ix Tech icon,
  which the sheet calls "Ixian Ambassador", and a Contract),
  Interstellar Shipping, Secrets, Smuggling, Tech Negotiation, every one
  printing "+1 Contract" -- and counts the standard 20 as Acquire 1,
  Arrakeen 2, Deliver Supplies 1, Espionage 2 (both 3 Solari), Harvest 3+ 2
  (both 3 Solari), Harvest 4+ 1, Heighliner 2, High Council 2, Immediate 1,
  Research Station 2, Sardaukar 2, Spice Refinery 2. Both totals match the
  rulebook's 20 + 10 [Main p. 16]. Spice Refinery I (draw two cards) and II
  (1 water) were read from their faces. Dune Cards Hub lists all 28 faces as
  "Uprising contract" with one copy each and no Rise of Ix flag, so it cannot
  settle membership or copies. `tests/unit/content/test_setup_manifests.py`
  pins the faces, the copies and "no standard tile prints +1 Contract".
- Setup replay, take/refill, partial and complete depletion, Immediate,
  board-space/Harvest/Acquire completion, all reward shapes, same-space multiple
  Contracts, no retroactive completion, Gather ordering, troop deployment,
  observation redaction, deterministic action replay, and codec round trips have
  regression tests.
- The eight Bloodlines tokens have their own regression file
  (`tests/unit/rules/test_bloodlines_contracts.py`, 2026-09-09).
