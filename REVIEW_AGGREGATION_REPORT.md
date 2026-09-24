# Phase 0.2B — Review Aggregation, Adjudication & Pattern Precision

Status: **REVIEW_COMPLETE**. Pinned validation scope: `{'extractor_version': '0.2.0', 'mapping_sha256': '3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a', 'source_set': {'scryfall': '0ce026779dae1a9a6448ef7a85e606d662343f5e', 'forge': 'cef86f363d7f7d5b3293248a75f550a7c3404066', 'xmage': '6212eb37907c1ce751d8a3fea8b3322056dc0264'}}`.

## Review coverage

Reviewer A inputs contain 460 raw rows and 460 unique IDs (expected 460); duplicate rows deduplicated: 0. Available unique Reviewer-A labels: `{'CORRECT': 459, 'WRONG': 1}`.
Reviewer B supplied 208 IDs (expected 208); 208 match the A files and 0 are absent. Exact-subset validation: **True**.
Forced audit: 1 separate item(s), labels `{'CORRECT': 1}`; excluded from primary counts and all precision calculations.

## Agreement

Reviewer-A labels: `{'CORRECT': 459, 'WRONG': 1}`. Reviewer-A file rows and unique IDs are reported above; this aggregation uses only the supplied authoritative result file(s).
Pre-adjudication agreement on all 208 blind items: raw 0.980769; Cohen's κ 0.0; Gwet's AC1 0.980396.
Reviewer A used one label category on this double-reviewed subset. Cohen's κ is degenerate under these marginals and is not interpreted as poor agreement; raw agreement and AC1 are reported alongside it.

## Adjudication

Accepted the four supplied recommendations as `WRONG`; 4 decisions are written to `adjudication_results.yaml`. Reviewer labels were checked against the supplied result files.

- `053d9fe47d105986611506c8` — `Campus Guide` / `forge.change_zone.v1`: Reviewer A `CORRECT`, Reviewer B `WRONG`, final `WRONG`. The sampled Forge occurrence has Origin=Library and Destination=Library. It performs within-library selection or repositioning rather than crossing a zone boundary, so this occurrence does not support zone_transition.
- `80e88eda5a088379b9af218a` — `Knowledge Exploitation` / `forge.change_zone.v1`: Reviewer A `CORRECT`, Reviewer B `WRONG`, final `WRONG`. The sampled Forge occurrence has Origin=Library and Destination=Library. It performs within-library selection or repositioning rather than crossing a zone boundary, so this occurrence does not support zone_transition.
- `23a6562a6e6a5c5879b55310` — `Neera, Wild Mage` / `forge.change_zone_all.v1`: Reviewer A `CORRECT`, Reviewer B `WRONG`, final `WRONG`. The sampled Forge occurrence has Origin=Library and Destination=Library. It performs within-library selection or repositioning rather than crossing a zone boundary, so this occurrence does not support zone_transition.
- `532892f8dc083b10a99ec57d` — `Aetherworks Marvel` / `forge.change_zone_all.v1`: Reviewer A `CORRECT`, Reviewer B `WRONG`, final `WRONG`. The sampled Forge occurrence has Origin=Library and Destination=Library. It performs within-library selection or repositioning rather than crossing a zone boundary, so this occurrence does not support zone_transition.

## Final primary results

Final labels: `{'CORRECT': 455, 'WRONG': 5}` (total 460). Forced audit labels remain separate.

## Pattern table

| pattern | population | probability n | CORRECT | TOO_BROAD | TOO_NARROW | CONTEXT_DEPENDENT | WRONG | AMBIGUOUS | SOURCE_EVIDENCE_INSUFFICIENT | decisive n | precision | interval | lower | upper |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| `forge.draw.v1` | 2458 | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 1.0 | `WILSON_BINOMIAL` | 0.8388748419471806 | 1.0 |
| `forge.token.v1` | 2230 | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 1.0 | `WILSON_BINOMIAL` | 0.8388748419471806 | 1.0 |
| `xmage.gain_life_effect.v1` | 684 | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 1.0 | `WILSON_BINOMIAL` | 0.8388748419471806 | 1.0 |
| `forge.deal_damage.v1` | 2070 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 30 | 1.0 | `WILSON_BINOMIAL` | 0.8864866068260312 | 0.9999999999999999 |
| `forge.destroy.v1` | 1205 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 30 | 1.0 | `WILSON_BINOMIAL` | 0.8864866068260312 | 0.9999999999999999 |
| `forge.put_counter.v1` | 1947 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 30 | 1.0 | `WILSON_BINOMIAL` | 0.8864866068260312 | 0.9999999999999999 |
| `xmage.damage_target_effect.v1` | 921 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 30 | 1.0 | `WILSON_BINOMIAL` | 0.8864866068260312 | 0.9999999999999999 |
| `xmage.destroy_target_effect.v1` | 705 | 30 | 29 | 0 | 0 | 0 | 1 | 0 | 0 | 30 | 0.9666666666666667 | `WILSON_BINOMIAL` | 0.8332960900859082 | 0.9940914096183874 |
| `xmage.add_counters_source_effect.v1` | 832 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 30 | 1.0 | `WILSON_BINOMIAL` | 0.8864866068260312 | 0.9999999999999999 |
| `forge.change_zone.v1` | 4136 | 40 | 38 | 0 | 0 | 0 | 2 | 0 | 0 | 40 | 0.95 | `WILSON_BINOMIAL` | 0.8349612263085903 | 0.9861793326138516 |
| `forge.change_zone_all.v1` | 467 | 40 | 38 | 0 | 0 | 0 | 2 | 0 | 0 | 40 | 0.95 | `FINITE_POPULATION_HYPERGEOMETRIC` | 0.8372591006423983 | 0.9914346895074947 |
| `xmage.exile_target_effect.v1` | 243 | 40 | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 40 | 1.0 | `FINITE_POPULATION_HYPERGEOMETRIC` | 0.9218106995884774 | 1.0 |
| `xmage.return_to_hand_source_effect.v1` | 117 | 40 | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 40 | 1.0 | `FINITE_POPULATION_HYPERGEOMETRIC` | 0.9316239316239316 | 1.0 |
| `cross.damage.deal_damage__damage_target_effect.v1` | 869 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 30 | 1.0 | `WILSON_BINOMIAL` | 0.8864866068260312 | 0.9999999999999999 |
| `cross.create_token.token__create_token_effect.v1` | 1196 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 30 | 1.0 | `WILSON_BINOMIAL` | 0.8864866068260312 | 0.9999999999999999 |

## Validation findings

The four supplied adjudications identify Forge `ChangeZone` / `ChangeZoneAll` occurrences with `Origin=Library` and `Destination=Library`; those occurrences reposition cards within the library and do not support a zone-boundary transition. The existing XMage unused-import lexical false positive is Reviewer A's `xmage.destroy_target_effect.v1` WRONG result in the supplied unique-ID subset. These findings do not change mappings or extractor behavior.

## Requirement-level status

No Requirement-level precision is calculated or combined. `requirement_evidence_projection.yaml` remains unchanged; source-specific pattern paths and cross corroboration are separate.

## Next-step blockers/findings

No input or adjudication blockers remain for this aggregation. The two findings above should be addressed as extractor guard candidates before expanding mappings; mappings and extractor behavior were left unchanged in this phase.
