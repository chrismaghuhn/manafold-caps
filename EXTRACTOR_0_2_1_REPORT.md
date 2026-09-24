# Extractor 0.2.1 — Guard Implementation

## Scope

Pinned revisions: Scryfall `0ce026779dae1a9a6448ef7a85e606d662343f5e`, Forge `cef86f363d7f7d5b3293248a75f550a7c3404066`, XMage `6212eb37907c1ce751d8a3fea8b3322056dc0264`. Mapping SHA-256 `3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a`. Extractor `0.2.0` to `0.2.1`.
Only the per-action Forge same-zone guard and XMage import-only guard were implemented. Source joins, mappings, and the historical Phase 0.2B review files remain unchanged.

## Forge same-zone guard

The pinned Phase 0.2C audit's 103 same-zone actions were all detected and suppressed individually. 98 matched action occurrences previously mapped to `zone_transition`; 98 were removed and 0 remain. Mixed records retain their other cross-zone actions.

## XMage import-only guard

All 6 imported-only mapped class records from the Phase 0.2C census were reproduced. 6 were mapped candidate evidence before the guard; 6 were removed and 0 remain. Instantiated, executable-reference, and unresolved usage is retained.

## Differential candidate impact

Removed mapped evidence occurrences: 104; added: 0. Removed distinct cards: 104; Oracle IDs: 104. By source: `{'forge': 98, 'xmage': 6}`. By construct: `{'ChangeZone': 80, 'ChangeZoneAll': 18, 'CounterTargetEffect': 1, 'CreateTokenEffect': 1, 'DestroyTargetEffect': 1, 'DrawCardSourceControllerEffect': 1, 'ExileTargetEffect': 1, 'ReturnToHandSourceEffect': 1}`. By requirement: `{'counter': 1, 'create_token': 1, 'destroy': 1, 'draw': 1, 'zone_transition': 100}`.
Unexpected removals: 0; unexpected additions: 0. The 104-occurrence Phase 0.2C estimate was recomputed from the candidate-set diff; actual removals are 104.

## Reviewed-sample regression

Final Phase 0.2B `CORRECT` sample removals: 0 / 455. Candidate paths removed in total: 5 (CORRECT 0, WRONG 5). Sample IDs and labels were not changed.

## Known-WRONG regression

Known WRONG samples: 5; fixed: 5; still emitted: 0. Fixed IDs: `['053d9fe47d105986611506c8', '23a6562a6e6a5c5879b55310', '532892f8dc083b10a99ec57d', '80e88eda5a088379b9af218a', '9e58403cc3d80c14b4c5a14c']`.

## Identity stability

Old unchanged identity set equals the new candidate identity set: **True**. Unchanged set size: 29182; SHA-256 `07335ad502e4512712de0af6e4d8cd7fb0322d0a49952fc9826c8cc66b20c36f`. Two complete pinned pipeline runs produced identical candidate, join, statistics, and semantic inventory outputs.

## Historical validation scope

Phase 0.2B results remain bound to extractor 0.2.0. Extractor 0.2.1 has NOT inherited Phase 0.2B confidence intervals automatically. No new precision or eligibility result was calculated.

## Differential validation requirements

Phase 0.2C.2 must review the differential under the 0.2.1 scope before any pattern precision is claimed. The 0.2B intervals cannot be carried forward. No new review samples were created in this phase.
