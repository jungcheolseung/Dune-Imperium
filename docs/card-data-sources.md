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

## UI display text

The browser UI's English effect text (`src/dune_imperium/display/`) is not a
transcription of printed card text. Structured content (the Intrigue effect
DSL, contract and conflict reward records, the static board-space effect
table) renders mechanically from the same data the engine executes; the
hand-authored parts — personal-card effect enum tokens, choice-driven board
spaces, and Leader abilities — take their wording from the image-verified
audit documents (`docs/implementation-audits/personal-cards.md`,
`docs/implementation-audits/leaders.md`) and the cited space table
(`docs/rules/board-spaces.md`). Coverage tests under `tests/unit/display/`
fail when new content lacks display text, so wording changes should update
the audit documents first and the display maps in the same work unit. Card
images are never committed. They live in the owner's private
`Dune-Imperium-assets` repository (never in this public one) as
`cards/<language>/<set>/<kind>/<printed name>.<ext>` — the file name is
the printed card name, same-name cards carry the printed distinguisher in
parentheses — and `cards/manifest.json` there is the only mapping between
those names and the engine's content IDs (plus each file's Dune Cards Hub
source URL and sha256). The server reads the manifest from the gitignored
`downloads/cards` symlink at start-up (`display/images.py`), prefers a
`ko/` scan per file over `en/`, and links only files that exist, so a
machine without the assets checkout serves the same catalog with text.
`tests/unit/display/test_images.py` pins that the manifest resolves all
170 Uprising content IDs when the checkout is linked. Every set directory
is self-contained: Uprising's four-player starting deck is the base
game's, unchanged, so `uprising/starting/` holds copies of the base-game
scans (the manifest notes the copy); the "Commander" variants Dune Cards
Hub files as "uprising-other" are six-player cards (Rules Supplements
p. 7, 14) and sit under `uprising/six-player/`; the three later Uprising promo
cards (Arrakis Revolt, The Beast's Spoils, Pivotal Gambit) sit under
`uprising/promo/` awaiting implementation; the other expansions' promo
cards sit under their own set's `promo/` (owner's classification). The other expansions in
the manifest are archived for future implementation with names derived
from the upstream slugs (`name_source: "upstream-slug"`, to be verified
against the images when that set is transcribed).
`uv run scripts/fetch_card_images.py` fills a checkout's gaps from the
manifest's sources.

The table UI (2026-09-03) adds two more machine-local, never-committed
assets under the same policy: the rulebook icon set (`downloads/icons/`,
45 transparent PNGs that `scripts/extract_rulebook_icons.py` cuts out of
the pinned official Uprising Main Rulebook by image xref — Icon Guide p. 20
and the Agent-icon list p. 9 — after verifying the file's sha256; names in
`display/icons.py`) and the owner's board scan (`map.jpg`, served at
`/board-image`). The browser renders the generated effect text through an
icon glossary (`ICON_RULES` in `static/app.js`): resources, troops, cards,
Influence, Persuasion, swords, Spies and the like become the printed icons
with the text kept as the tooltip, and without the icon set the words show
as-is. Hotspot and observation-post coordinates live in
`display/board_layout.py` as percentages of the scan and are pinned by
tests to cover all 22 spaces and 13 posts. Both assets are mirrored in the
private `Dune-Imperium-assets` repository (`icons/`, `board/`).

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
- DIU records Leverage's second reward as drawing one personal card. The
  printed card shows the CHOAM Contract icon (identical to Reach Agreement's),
  so the local transcription takes one Contract.
- DIU's Shadow Alliance condition is four Influence with any Faction. The
  printed card adds "where an opponent has the Alliance", so the local
  condition requires an opponent-held Alliance on that track.

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

The fourth batch transcribes Cunning and Special Mission from their card
images. Special Mission's first half places a Spy on a Bene Gesserit-connected
post (the purple Faction disc on the card); DIU's `target: "blue"` is read the
same way.

The fifth batch transcribes Weirding Combat, Questionable Methods and Find
Weakness from their card images; all three match DIU's shapes.

The sixth batch transcribes Devour, Go to Ground, Spice is Power, Tactical
Option and Reach Agreement from their card images. DIU's `retreat` cost with
`amount: [1, 2]` / `"any"` maps to `RetreatTroops(1, 2)` / `RetreatTroops(1, None)`.

The seventh batch transcribes Impress and Inspire Awe from their card images
alone (no DIU working copy was present). Both cards print an acquisition cap
of 3; the development handoff had recorded 4 for Impress, so the image was
re-checked at crop level before transcription. Inspire Awe's sandworm
sentence is modeled as a destination override on the acquisition reward, not
as a separate conditional section.

The eighth batch transcribes Call to Arms from its card image ("During your
Reveal turn this round, whenever you acquire a card:" plus a troop icon) as
the first face-up triggered option. DIU (available locally again) models it
as a `conditional_reward` with a `buy_imperium` condition, which matches the
local per-acquisition trigger reading.

The ninth batch transcribes Distraction from its card image ("When you
deploy three or more units to the Conflict in a single turn:" then "You may
place this Spy on the same observation post as another player's Spy."). DIU
models it as a `deploy_units amount 3` condition with a `shared_post` Spy
reward, matching the local trigger and the shared-post placement.

The tenth batch transcribes Leverage from its card image ("If you gained
spice this turn:" then the CHOAM Contract icon and a one-Solari coin). DIU's
`gained_resource_this_turn` check matches, but its reward list gives one
Solari and a personal-card draw; the left icon is identical to Reach
Agreement's printed Contract icon, so the local transcription takes a
Contract instead.

The eleventh batch transcribes the six Endgame cards from their images.
Crysknife, Desert Mouse and Ornithopter print a one-Spice hexagon as the
Plot half and "Flip one of your face-up [icon] or [wild] Conflict cards"
into the golden Victory Point sphere as the Endgame half (the Ornithopter
image slug is misspelled "ornitopter" on Dune Cards Hub). CHOAM Profits
requires "four or more contracts", Secure Spice Trade "at least two The
Spice Must Flow" for one Victory Point plus two Spice, and Shadow Alliance
"4 Influence (or more) on a Faction track where an opponent has the
Alliance". DIU agrees on every shape except Shadow Alliance, where it drops
the opponent-Alliance clause.

The twelfth batch closes the deck with Manipulate and Spring the Trap.
Spring the Trap prints two Spy-recall arrows into seven swords, exactly as
DIU records it. Manipulate's text is transcribed from its image; DIU models
the card as an opaque custom `manipulate` effect, so the local set-aside
zone, discount and expiry follow the printed card and the FAQ p. 3 ruling.

