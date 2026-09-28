# Analysis guide: reading the Arrakeen Scouts code in Dire Wolf Game Room

Written for the analysis agents of 2026-09-27. Run the tools from this folder
(`scripts/dwgr/`) with UnityPy, TypeTreeGeneratorAPI and capstone available (see
README.md). The game is Unity 2022.3.62f2, IL2CPP, macOS x86_64 dylib (stripped).
Namespace of the Dune companion: `grm.companions.spice` (assembly `companions-shared`).
"Arrakeen Scouts" = the 3-4 player mode (GameMode MESA = 3) with a random "schedule"
of beats: subcommittees, missions, events, auctions, sales.

## Tools (all resolve names from global-metadata + binary; addresses are file offsets == vmaddr)
- `il2dis.py <method-name-substring | 0xADDR> ...` — annotated x86-64 disassembly of whole function(s).
  Comments show: called method names (incl. shared generic instances, e.g. `System.Linq.Enumerable::Where<object>`),
  lazily-initialised metadata globals decoded (`TypeInfo:...`, `MethodRef:...`, `MethodDef:...`, `Str:'literal'`,
  `FieldInfo:...`), float constants (`f32=`), and runtime helpers prefixed `rt:`.
  Example: `python il2dis.py "ScheduleController::pickEvents"`
- `il2fields.py <FullTypeName> | <prefix*>` — field offsets (+hex/decimal as printed are DECIMAL), field types, enum constant
  values, and method addresses of a type. Nested types use `/`, e.g. `grm.companions.spice.ScheduleController/<>c`.
  Example: `python il2fields.py grm.companions.spice.EventDefinition grm.companions.spice.ScheduleBeatDefinition`
- `il2xref.py <method-name-substring | 0xADDR>` — direct call/jmp sites (E8/E9) into that function, with the owning method.
  Indirect uses (delegates, virtual calls) are NOT found; search for the `MethodDef:`/`MethodRef:` global in disassembly instead.

## IL2CPP x86-64 reading conventions
- SysV ABI: instance methods get `this` in rdi, then rsi, rdx, rcx, r8, r9; the LAST argument is the hidden `MethodInfo*`
  (for generic instances it is the `MethodRef:` global loaded right before the call). Return in eax/rax/xmm0.
- Object header is 16 bytes (klass, monitor). Field offsets from il2fields.py are absolute offsets from the object pointer.
- `T[]` arrays: length (uint64/int) at +0x18, elements start at +0x20 (8 bytes per reference element, 4 per int).
- `List<T>`: `_items` (T[]) at +0x10, `_size` at +0x18, `_version` at +0x1c. `get_Count`/`get_Item` are usually INLINED
  (you will see reads of +0x18 and bounds checks rather than calls).
- `string`: length int32 at +0x10, UTF-16 chars at +0x14.
- Static fields: `mov rax,[TypeInfo global]` → klass; `[klass+0xb8]` → static-fields block; `cmp dword [klass+0xe0],0`
  checks cctor-finished. Lambdas live in the `<>c` nested class; cached delegate in its static fields.
- Virtual/interface calls load a function pointer from the object's klass (`mov rax,[obj]` then `call [rax+off]`).
  Identify them from context/next MethodRef where possible and say when you are inferring.
- Helpers (labelled only for build 84d64e12…, see HELPERS_BY_BUILD in il2dis.py): rt:initialize_runtime_metadata (lazy init block at function start — ignore), rt:object_new, rt:SZArrayNew,
  rt:write_barrier (after storing a reference field — ignore), rt:throw_* (noreturn error paths — ignore).
- `UnityEngine.Random::Range(int min, int max)` returns min..max-1 (max EXCLUSIVE); `Range(float,float)` is inclusive.
  `System.Random` may also be used — check which. `bool` fields are single bytes (`cmp byte ptr [...]`).

## Data extracted (`extract.py <out_dir>`; locally `assets/reference/dwgr-arrakeen-scouts/data`)
- `spice_mb/<Class>.json` — every spice MonoBehaviour/ScriptableObject instance, parsed with generated typetrees.
  Definitions: SubcommitteeDefinition.json, MissionDefinition.json, EventDefinition.json, AuctionDefinition.json,
  SaleDefinition.json (each has `_path_id` in resources.assets). `ScheduleController.json` = the 8 schedule configs;
  `schedules.json` names them by the SpiceDataController field they hang on (base … Uprising+Ix+Immortality).
- `beats_bundle.txt` — per definition: raw fields, which of the 8 schedules include it, all localization strings it uses
  (EN + official KO, sprite indices expanded to names), and the UI prefab tree(s) (GameObject hierarchy with texts,
  TMPLocalizer keys, icon sprite names, 3D token mesh/material names, anchored positions @[x,y]). Prefabs under a prompt
  named `..._Uprising` are the Uprising UI; others are the base-game UI. "(image disabled)" marks an Image component
  that is not drawn.
  NOTE: a TEXT value that sits next to a TMPLocalizer is only the editor-baked placeholder; at runtime the localizer
  replaces it with the loc string for `locKey`. Baked placeholders are often stale copy-paste (e.g. "Fold Space" text in
  unrelated events) — trust loc + icons, and report conflicts.
- `loc/<lang>.json` — localization (every spice.* key plus keys the spice prefabs use), 13 languages. Text sprites: `<sprite index=N>` map:
  0 TrashCard 1 DrawCard 2 IntrigueCard 3 Mentat 4 Agent 5 VictoryPoint 6 Troop 7 Water 8 Solari 9 Spice 10 Persuasion
  11 Strength 12 IntrigueTrash 13 BonusSpice 14 SignetRing 15 Pentagon 16 Circle 17 Triangle 18 Faction_Emperor
  19 Faction_SpacingGuild 20 Faction_Fremen 21 Faction_BeneGesserit 22 RankUp_SpacingGuild 23 RankUp_Emperor
  24 RankUp_BeneGesserit 25 RankUp_Wild(+1 any) 26 RankUp_Fremen 27 RankUp2_Fremen 28 RankUp2_BeneGesserit
  29 RankUp2_Emperor 30 RankUp2_Wild(+2 any) 31 Solari_1 32 Solari_2 33 Solari_3 34 Spice_1 35 Spice_2 36 Spice_3
  37-40 generic glyphs (used for Agent / Scout button / discard depending on text) 41 Dreadnought 42 Helix 43 Specimen
  44 Beetle 45 Research 48 Sword 49 Contract 50 Recall 51 TrashIntrigue 52 Discard 53 Spy 54 Arrow 55 Persuasion_2
  56 RecallAgent 57 Spice_4. `<sprite name=X>` uses the name directly (e.g. Spice_2 = 2 spice).
- Board-space names and Uprising rules: the main repository's docs/rules/.
