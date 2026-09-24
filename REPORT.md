# Manafold CAP miner — Phase 0.1.2 Suspicious Join Audit

Generated: 2026-09-24T07:44:31.348651+00:00 UTC

## Dataset inventory

### scryfall: `nishtahir/scryfall-oracle-cards`

Revision: `0ce026779dae1a9a6448ef7a85e606d662343f5e` (pinned snapshot). Rows: **36,923**. Splits: `{'train': 36923}`.
Columns: `reprint`, `all_parts`, `textless`, `rulings_uri`, `flavor_text`, `image_uris`, `set_id`, `card_faces`, `power`, `life_modifier`, `set_search_uri`, `watermark`, `artist`, `tcgplayer_id`, `cmc`, `oracle_id`, `edhrec_rank`, `content_warning`, `set_type`, `loyalty`, `flavor_name`, `nonfoil`, `preview`, `attraction_lights`, `collector_number`, `game_changer`, `highres_image`, `keywords`, `oracle_text`, `games`, `resource_id`, `set_name`, `released_at`, `uri`, `digital`, `frame_effects`, `id`, `security_stamp`, `prices`, `colors`, `multiverse_ids`, `color_identity`, `scryfall_set_uri`, `type_line`, `variation`, `reserved`, `purchase_uris`, `printed_type_line`, `lang`, `border_color`, `toughness`, `defense`, `name`, `layout`, `color_indicator`, `object`, `set`, `related_uris`, `illustration_id`, `foil`, `legalities`, `booster`, `story_spotlight`, `rarity`, `oversized`, `hand_modifier`, `finishes`, `frame`, `prints_search_uri`, `mtgo_foil_id`, `card_back_id`, `set_uri`, `scryfall_uri`, `produced_mana`, `promo_types`, `mana_cost`, `arena_id`, `mtgo_id`, `artist_ids`, `cardmarket_id`, `image_status`, `promo`, `penny_rank`, `tcgplayer_etched_id`, `full_art`, `printed_text`

### forge: `404NotF0und/MtG-json-to-ForgeScript`

Revision: `cef86f363d7f7d5b3293248a75f550a7c3404066` (pinned snapshot). Rows: **27,286**. Splits: `{'train': 19100, 'validation': 2729, 'test': 5457}`.
Columns: `instruction`, `input`, `output`, `text`

### xmage: `Frogski/xMageData`

Revision: `6212eb37907c1ce751d8a3fea8b3322056dc0264` (pinned snapshot). Rows: **18,985**. Splits: `{'train': 18985}`.
Columns: `prompt`, `completion`

Python package versions: `{'datasets': '5.0.1', 'huggingface_hub': '1.32.0', 'PyYAML': '6.0.3'}`. Cache/materialization timestamp: `2026-09-24T07:43:08.430573+00:00` UTC. Mining is pinned to the Phase 0.1.0 revisions listed above; if the current Hub head has moved, it is recorded but not substituted.

## Calibration summary

Exact-identity matching: Forge 26,384/36,923 (71.46%); XMage 18,252/36,923 (49.43%); both 17,270 (46.77%). Ambiguous records: 1,520.
Cards with implementation evidence and at least one mapped requirement: 16,341/27,366 (59.71%).
Seed mapping SHA-256: `3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a`. Extractor version: `0.2.0`.

## Card-level resolution

Card counts are distinct Scryfall Oracle identities, not requirement rows. A card with external evidence is `fully_unresolved` when none of its extracted semantic tokens/classes map; `partially_resolved` when it has both mapped and unmapped evidence. Lexical extraction cannot demonstrate completeness, so `fully_resolved` is conservatively zero. Cards with mapped evidence and no observed unmapped semantic token are shown separately as `resolution_completeness_unverified`.

- Total Oracle identities: **36,923**
- With any external evidence: **27,366**
- With Forge / XMage / both: **26,384 / 18,252 / 17,270**
- With any mapped requirement: **16,341**
- Fully unresolved: **11,025**
- Partially resolved: **14,401**
- Fully resolved: **0**
- Completeness unverified: **1,940**

## Requirement-level evidence

These counts are mapped requirement candidates (card × generic kind), not cards. `MULTI_IMPLEMENTATION_AGREEMENT` means Forge and XMage independently expose constructs mapped by the seed map to the same generic candidate. It does not mean rules-correct, human-verified, or high-confidence. Every candidate remains `rules_evidence: NOT_CHECKED` and `review_status: UNREVIEWED`.

- Total mapped candidates: **21,251**
- Multi-implementation agreement: **5,828**
- Forge only: **14,669**
- XMage only: **754**
- Unmapped evidence attached to matched cards: Forge 38,338 action occurrences; XMage 51,585 semantic class occurrences; cards affected 24,585.

## Mapping coverage

Coverage denominators include all records in each pinned source corpus; Forge actions count parsed action occurrences, while each XMage class counts at most once per implementation record. Structural Java bases, targets, and filters are excluded from the XMage semantic-class denominator.

### forge

Unique extracted types: 329; mapped: 16; unmapped: 313.
Occurrences: 23,847/64,028 mapped (37.24%).

### xmage

Unique extracted types: 7,109; mapped: 13; unmapped: 7,096.
Occurrences: 6,953/61,146 mapped (11.37%).

## Oracle mismatch audit

Identity matching remains exact and deterministic. Text similarity is used only after an exact-name/Oracle-ID join to label diagnostics; it never establishes identity. Classifier categories are hypotheses or exact-normalization diagnostics, not text repairs.

Calibration found that some XMage multiface prompts contain a separate `Oracle Text:` block after a second face's `Name:` and other fields. The earlier extractor could absorb that metadata into the first face's text. The 0.1.1 parser now stops at prompt field boundaries and combines all face text blocks. In this pinned run, the prior 80 `LIKELY_PROMPT_EXTRACTION_ARTIFACT` records disappear; 144 source texts now exactly match the combined face representation. No dataset text was changed.

### forge

Mismatches: 12,380; assigned a diagnostic category: 12,342 (99.69%); text-diagnostic `UNCLASSIFIED`: 38; sent to the Phase 0.1.2 identity audit: 38.

| category | count | % of mismatches |
|---|---:|---:|
| `EXACT_AFTER_CARDNAME_TEMPLATE_NORMALIZATION` | 5,453 | 44.05% |
| `EXACT_AFTER_REMINDER_TEXT_REMOVAL` | 706 | 5.70% |
| `LIKELY_FORMATTING_DIFFERENCE` | 10 | 0.08% |
| `LIKELY_STALE_ORACLE_WORDING` | 6,173 | 49.86% |
| `UNCLASSIFIED` | 38 | 0.31% |

### xmage

Mismatches: 9,639; assigned a diagnostic category: 9,619 (99.79%); text-diagnostic `UNCLASSIFIED`: 20; sent to the Phase 0.1.2 identity audit: 20.

| category | count | % of mismatches |
|---|---:|---:|
| `EXACT_AFTER_CARDNAME_TEMPLATE_NORMALIZATION` | 5,717 | 59.31% |
| `EXACT_AFTER_FACE_TEXT_COMPARISON` | 144 | 1.49% |
| `EXACT_AFTER_REMINDER_TEXT_REMOVAL` | 240 | 2.49% |
| `LIKELY_FORMATTING_DIFFERENCE` | 1 | 0.01% |
| `LIKELY_STALE_ORACLE_WORDING` | 3,255 | 33.77% |
| `MULTIFACE_REPRESENTATION_DIFFERENCE` | 262 | 2.72% |
| `UNCLASSIFIED` | 20 | 0.21% |

Exact diagnostic normalization explains 12,260/22,019 mismatches (55.68%): equality after reminder-text removal, card-name/self-template normalization, or face-text comparison. Another 9,701 receive a heuristic diagnostic such as likely stale wording or possible bad join. In total 21,961/22,019 (99.74%) have a non-`UNCLASSIFIED` category; **58** remain unclassified by that text heuristic. All 58 exact-identity cases were then individually classified in `JOIN_AUDIT.md` and `data/output/suspicious_join_audit.json`. Categories and up to 20 sorted examples per category are in `data/output/oracle_mismatch_audit.json`.

## Top unmapped vocabulary

Examples are the first five distinct names in normalized alphabetical order; token counts are deterministic corpus occurrence counts.

### Forge actions

| token | count | example_card_names |
|---|---|---|
| ChangesZone | 5519 | A-Acererak the Archlich; A-Baleful Beholder; A-Blood Artist; A-Brine Comber; A-Cauldron Familiar |
| Continuous | 4112 | +2 Mace; A-Alrund, God of the Cosmos; A-Ancestral Katana; A-Armory Veteran; A-Binding Geist |
| Pump | 4112 | A-Asari Captain; A-Binding Geist; A-Blessed Hippogriff; A-Bretagard Stronghold; A-Bruenor Battlehammer |
| Cleanup | 2346 | A-Akki Ronin; A-Ardent Dustspeaker; A-Demilich; A-Ellywick Tumblestrum; A-Elven Bow |
| Phase | 1799 | A-Alrund, God of the Cosmos; A-Cosmos Elixir; A-Death-Priest of Myrkul; A-Dreamshackle Geist; A-Geology Enthusiast |
| Effect | 1422 | A-Ardent Dustspeaker; A Display of My Dark Power; A-Ellywick Tumblestrum; A-Glamorous Outlaw; A-Harald Unites the Elves |
| Attach | 1315 | A-Ancestral Katana; A-Binding Geist; A-Brine Comber; A-Bruenor Battlehammer; A-Dorothea, Vengeful Victim |
| Attacks | 1095 | A-Acererak the Archlich; A-Akki Ronin; A-Ancestral Katana; A-Ardent Dustspeaker; A-Asari Captain |
| SpellCast | 1013 | A-Devoted Grafkeeper; A-Dragon's Rage Channeler; A-Hullbreaker Horror; A-Master of Winds; A-Mentor's Guidance |
| Animate | 870 | A-Capenna Express; A-Druid Class; A-Faceless Haven; A-Kargan Intimidator; A-Kenku Artificer |
| PumpAll | 839 | A-Baleful Beholder; A-Cabaretti Charm; A-Steadfast Unicorn; A-The Meathook Massacre; A-Urza's Command |
| Dig | 736 | A-Alrund, God of the Cosmos; A-Ardent Dustspeaker; A-Demon's Due; A-Ellywick Tumblestrum; A-Harald, King of Skemfar |
| DamageDone | 695 | A-Alrund, God of the Cosmos; A-Briar Hydra; A-Dokuchi Silencer; A-Goggles of Night; A-Krydle of Baldur's Gate |
| Sacrifice | 692 | A-Baleful Beholder; A-Minsc & Boo, Timeless Heroes; Abhorrent Overlord; Abyssal Gatekeeper; Abyssal Gorestalker |
| Charm | 516 | A-Baleful Beholder; A-Cabaretti Charm; A-Dawnbringer Cleric; A-Dreamshackle Geist; A-Exhibition Magician |
| Counter | 466 | A-Emerald Dragon; Abjure; Absorb; Absorb Energy; Abstruse Interference |
| Mill | 430 | A-Circle of the Land Druid; A-Deal Gone Bad; A-Devoted Grafkeeper; A-Druidic Ritual; A-Harald Unites the Elves |
| Scry | 413 | A-Alrund, God of the Cosmos; A-Cosmos Elixir; A-Glamorous Outlaw; A-Goggles of Night; A-Krydle of Baldur's Gate |
| ChooseCard | 406 | A-Fall of the Impostor; A-Incriminate; A-Nahiri, Heir of the Ancients; Agitator Ant; Ajani's Aid |
| DelayedTrigger | 400 | A-Dorothea, Vengeful Victim; A-Moss-Pit Skeleton; A-Ochre Jelly; Abomination; Abuelo, Ancestral Echo |

### XMage semantic classes

| class | count | example_card_names |
|---|---|---|
| FlyingAbility | 2186 | Aarakocra Sneak; Abbey Gargoyles; Abbey Griffin; Aberrant Researcher; Abhorrent Overlord |
| TapSourceCost | 2044 | Abbey Matron; Abstergo Entertainment; Abstruse Archaic; Abuna Acolyte; Abundant Growth |
| GenericManaCost | 1204 | Abstergo Entertainment; Abstruse Archaic; Abstruse Interference; Access Tunnel; Ace's Baseball Bat |
| BoostSourceEffect | 827 | Abbey Matron; Abyssal Nocturnus; Adanto Vanguard; Adarkar Sentinel; Aerial Engineer |
| BoostTargetEffect | 825 | Abandon Reason; Abnormal Endurance; Accelerated Mutation; Acrobatic Leap; Act of Heroism |
| TrampleAbility | 820 | Abaddon the Despoiler; Aberrant; Abominable Treefolk; Abyssal Persecutor; Aetherstream Leopard |
| AttachEffect | 761 | Abduction; Aboshan's Desire; Abundant Growth; Abzan Runemark; Acquired Mutation |
| EnchantAbility | 744 | Abduction; Aboshan's Desire; Abundant Growth; Abzan Runemark; Acquired Mutation |
| GainAbilityTargetEffect | 713 | A Killer Among Us; Abandon Reason; Abnormal Endurance; Academic Dispute; Accelerate |
| HasteAbility | 688 | Accelerate; Act of Aggression; Act of Treason; Adeliz, the Cinder Wind; Admiral Brass, Unsinkable |
| SacrificeTargetCost | 669 | Abjure; Ace, Fearless Rebel; Acolyte of Aclazotz; Agency Coroner; Agent of Shauku |
| SacrificeSourceCost | 631 | A Killer Among Us; Abandoned Outpost; Abzan Banner; Acidic Sliver; Adric, Mathematical Genius |
| BeginningOfUpkeepTriggeredAbility | 611 | Aberrant Researcher; Abhorrent Overlord; Abzan Beastmaster; Act of Authority; Aether Rift |
| GainAbilitySourceEffect | 549 | Abyssal Nocturnus; Abzan Kin-Guard; Adanto Vanguard; Advanced Hoverguard; Aerial Engineer |
| VigilanceAbility | 508 | Abbey Griffin; Abomination of Llanowar; Abstruse Archaic; Abzan Runemark; Accorder's Shield |
| AttacksTriggeredAbility | 488 | Ace, Fearless Rebel; Acererak the Archlich; Aclazotz, Deepest Betrayal; Acolyte Hybrid; Aerial Guide |
| ConditionalInterveningIfTriggeredAbility | 478 | Abzan Beastmaster; Acclaimed Contender; Acererak the Archlich; Adherent of Hope; Aerial Surveyor |
| BoostControlledEffect | 461 | A Tale for the Ages; Achilles Davenport; Adeliz, the Cinder Wind; Agatha of the Vile Cauldron; Ajani, Wise Counselor |
| ConditionalContinuousEffect | 461 | Abaddon the Despoiler; Aboshan's Desire; Abzan Kin-Guard; Abzan Runemark; Ace's Baseball Bat |
| FirstStrikeAbility | 459 | Abandon Reason; Abattoir Ghoul; Ace's Baseball Bat; Advance Scout; Aerial Maneuver |

## Phase 0.1.2 join decisions

The pinned suspicious set contains 58 individually reviewed records: {'KEEP_JOIN': 49, 'KEEP_WITH_FLAG': 9, 'REJECT_JOIN': 0}. No join was rejected. 0 decisions remain unresolved. Nine XMage records are retained with warnings because their type-line dash is mojibake; warning metadata is attached to their matched evidence.
Identity counts and mapped candidate counts did not change: before/after Forge 26384/26384, XMage 18252/18252, both 17270/17270; mapped candidates 21251/21251.

## Interpretation and next decision

The 0.1.1 seed mappings changed candidate-level cross-engine agreement from the 0.1.0 baseline of 2,962 to 5,828. This is a count of mapped candidate pairs, not a correctness score.
All audited identities were supported by an exact unique normalized card name and matching card context. Oracle wording variants are retained; nine encoding warnings remain visible on XMage evidence. No name collision, face collision, or matching-policy defect was found. The audited identity joins are suitable for Phase 0.2 while preserving those warnings.

No rules validation, eligibility policy, or CAP integration was added. Forge and XMage remain implementation evidence, not semantic authority. No LLM or embeddings are used.
