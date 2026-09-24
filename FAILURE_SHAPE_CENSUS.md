# Phase 0.2C — Failure-Shape Census & Guard Design

## Scope

Pinned revisions: Scryfall `0ce026779dae1a9a6448ef7a85e606d662343f5e`, Forge `cef86f363d7f7d5b3293248a75f550a7c3404066`, XMage `6212eb37907c1ce751d8a3fea8b3322056dc0264`. Extractor `0.2.0`; mapping SHA-256 `3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a`.
This is an analysis-only full-corpus census. The miner, mappings, sample IDs, and Phase 0.2B precision results are unchanged.

## Phase 0.2B findings being investigated

Phase 0.2B recorded four WRONG Forge samples involving same-library movement and one WRONG XMage sample where `DestroyTargetEffect` appeared as an import without executable use. These are extractor-candidate false positives; they do not by themselves invalidate the generic mappings.

## Forge same-zone census

Scanned 27,286 pinned Forge source records. Parsed ChangeZone-family actions: `{'ChangeZone': 5242, 'ChangeZoneAll': 575}`. All parsed action occurrences were retained in the classification census; 103 are unambiguous SAME_ZONE occurrences, of which 98 join to a Scryfall identity and currently map to `zone_transition`.
Distinct affected cards: 98; distinct Oracle IDs: 98. Classification counts: `{'CROSS_ZONE': 5445, 'ORIGIN_MISSING': 15, 'ORIGIN_OR_DESTINATION_MULTI_VALUED': 96, 'OTHER_UNRESOLVED': 158, 'SAME_ZONE': 103}`.

| action | origin | destination | count |
|---|---|---|---:|
| ChangeZone | Library | Library | 81 |
| ChangeZoneAll | Library | Library | 22 |

Descriptive same-zone subgroups (non-exclusive cues assigned by priority): `{'BOTTOM_OF_LIBRARY_REPOSITIONING': 11, 'LIBRARY_SEARCH_OR_REVEAL_STAGING': 3, 'RANDOM_ORDER_REINSERTION': 17, 'REMEMBERED_CARD_CLEANUP': 29, 'TOP_OF_LIBRARY_REPOSITIONING': 43}`. These are not semantic conclusions; unresolved evidence remains `UNCLASSIFIED`.

Reviewed failure traceability:

- `053d9fe47d105986611506c8` — Campus Guide: captured=True, source `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00006322`.
- `23a6562a6e6a5c5879b55310` — Neera, Wild Mage: captured=True, source `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00015991`.
- `532892f8dc083b10a99ec57d` — Aetherworks Marvel: captured=True, source `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00009329`.
- `80e88eda5a088379b9af218a` — Knowledge Exploitation: captured=True, source `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00026347`.

## Forge hypothetical guard impact

The counterfactual guard removes 98 currently mapped SAME_ZONE action occurrences across 98 cards / 98 Oracle IDs. Patterns: `['forge.change_zone.v1', 'forge.change_zone_all.v1']`.
Among primary review samples: 4 changed; CORRECT=0, WRONG=4. This counterfactual does not recalculate precision.

## XMage mapped-class usage census

Scanned 18,985 pinned XMage source records and all 13 mapped classes from `mappings.yaml`. Across joined candidate records, 6 extracted class-record occurrences are imported only, affecting 6 cards / 6 Oracle IDs and 6 mappings. The all-source imported-only count is 6.

| mapped class | requirement | source records mentioning class | extracted records | imported only | instantiated | executable use | unresolved | cards affected |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `AddCountersSourceEffect` | `counter_change` | 874 | 873 | 0 | 873 | 0 | 0 | 0 |
| `CounterTargetEffect` | `counter` | 154 | 153 | 1 | 151 | 1 | 0 | 1 |
| `CreateTokenEffect` | `create_token` | 1441 | 1441 | 1 | 1438 | 2 | 0 | 1 |
| `DamageAllEffect` | `damage` | 130 | 130 | 0 | 130 | 0 | 0 | 0 |
| `DamageTargetEffect` | `damage` | 955 | 955 | 0 | 954 | 1 | 0 | 0 |
| `DestroyAllEffect` | `destroy` | 121 | 121 | 0 | 121 | 0 | 0 | 0 |
| `DestroyTargetEffect` | `destroy` | 728 | 728 | 1 | 725 | 2 | 0 | 1 |
| `DrawCardSourceControllerEffect` | `draw` | 1277 | 1277 | 1 | 1276 | 0 | 0 | 1 |
| `ExileTargetEffect` | `zone_transition` | 255 | 255 | 1 | 254 | 0 | 0 | 1 |
| `GainLifeEffect` | `gain_life` | 717 | 717 | 0 | 717 | 0 | 0 | 0 |
| `LoseLifeTargetEffect` | `lose_life` | 174 | 174 | 0 | 174 | 0 | 0 | 0 |
| `ReturnToHandSourceEffect` | `zone_transition` | 122 | 122 | 1 | 121 | 0 | 0 | 1 |
| `UntapLandsEffect` | `untap` | 7 | 7 | 0 | 7 | 0 | 0 | 0 |

Known false positive reproduced: `9e58403cc3d80c14b4c5a14c` / Invasion of New Capenna // Holy Frazzle-Cannon / `DestroyTargetEffect` = `IMPORTED_ONLY` (captured=True); source `xmage@6212eb37907c1ce751d8a3fea8b3322056dc0264:row:00007534`.
Non-executable context diagnostics: `{'comment_occurrences': 1, 'string_literal_occurrences': 0, 'comment_or_string_only_records': 1, 'import_only_records': 6, 'package_mentions': 0}`. Comments, strings, imports, and package declarations are not treated as executable usage.

## XMage hypothetical guard impact

The counterfactual guard removes 6 joined mapped class-record occurrences, affecting 6 cards / 6 Oracle IDs. Mapping paths affected: `['xmage:CounterTargetEffect -> counter', 'xmage:CreateTokenEffect -> create_token', 'xmage:DestroyTargetEffect -> destroy', 'xmage:DrawCardSourceControllerEffect -> draw', 'xmage:ExileTargetEffect -> zone_transition', 'xmage:ReturnToHandSourceEffect -> zone_transition']`. Selected validation patterns affected: `['cross.create_token.token__create_token_effect.v1', 'xmage.destroy_target_effect.v1', 'xmage.exile_target_effect.v1', 'xmage.return_to_hand_source_effect.v1']`.
Among primary review samples: 1 changed; CORRECT=0, WRONG=1.

## Review-sample impact

Labels use Phase 0.2B Reviewer-A outcomes with the four accepted adjudications applied. Forced audit is excluded. A sample is counted only when the guard removes its selected mapping construct from that source record; cross-engine examples are affected only on the corresponding evidence path. Both guards are counterfactual only.

## Combined counterfactual impact

Union after occurrence/card/Oracle deduplication: 104 mapped occurrences, 104 distinct cards, 104 Oracle IDs; requirements `['counter', 'create_token', 'destroy', 'draw', 'zone_transition']`; selected validation patterns `['cross.create_token.token__create_token_effect.v1', 'forge.change_zone.v1', 'forge.change_zone_all.v1', 'xmage.destroy_target_effect.v1', 'xmage.exile_target_effect.v1', 'xmage.return_to_hand_source_effect.v1']`; mapping paths `['forge:ChangeZone -> zone_transition', 'forge:ChangeZoneAll -> zone_transition', 'xmage:CounterTargetEffect -> counter', 'xmage:CreateTokenEffect -> create_token', 'xmage:DestroyTargetEffect -> destroy', 'xmage:DrawCardSourceControllerEffect -> draw', 'xmage:ExileTargetEffect -> zone_transition', 'xmage:ReturnToHandSourceEffect -> zone_transition']`.
Reviewed sample union: 5 samples, CORRECT=0, WRONG=5.

## Guard design recommendation

Forge guard: `CANDIDATE`. XMage guard: `CANDIDATE`. Neither is approved or implemented. See `guard_design.yaml` for explicit predicates, counts, limitations, and recommendations.

## Validation consequences

The 0.2B estimates remain bound to extractor 0.2.0 and are historical. No adjusted precision, interval, or Requirement-level score was calculated. Any future guard implementation needs a new extractor version, a source-occurrence differential, and validation under a new scope.

## Next phase

A narrowly scoped guard implementation can be considered after reviewing this census. The evidence distinguishes mapping correctness from candidate extraction: genuine `DestroyTargetEffect` uses may still map to `destroy`; only import-only records should cease to count. Likewise, `ChangeZone` remains a useful zone-transition signal when endpoints differ; this census only identifies same-zone occurrences for review.
