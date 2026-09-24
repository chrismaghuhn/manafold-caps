# Phase 0.2B — Review Aggregation, Adjudication & Pattern Precision

Status: **BLOCKED_INPUT_INCOMPLETE**. Pinned validation scope: `{'extractor_version': '0.2.0', 'mapping_sha256': '3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a', 'source_set': {'scryfall': '0ce026779dae1a9a6448ef7a85e606d662343f5e', 'forge': 'cef86f363d7f7d5b3293248a75f550a7c3404066', 'xmage': '6212eb37907c1ce751d8a3fea8b3322056dc0264'}}`.

## Review coverage

Reviewer A inputs contain 450 raw rows and 300 unique IDs (expected 460); duplicate rows deduplicated: 150. Available unique Reviewer-A labels: `{'CORRECT': 299, 'WRONG': 1}`.
Reviewer B supplied 208 IDs (expected 208); 48 match the A files and 160 are absent. Exact-subset validation: **False**.
Forced audit: 1 separate item(s), labels `{'CORRECT': 1}`; excluded from primary counts and all precision calculations.

## Agreement

Available Reviewer-A labels: `{'CORRECT': 299, 'WRONG': 1}`; expected when complete: 459 CORRECT and 1 WRONG.
The supplied A-150 file duplicates the 150-item pilot contained in the cumulative A-300 file. Of 160 missing A IDs, 4 have an A label only in the disagreement artifact; 156 have no A label in any supplied result file.
Agreement metrics were not calculated because the supplied Reviewer-A files are incomplete and Reviewer B's IDs are not an exact subset of A. The disagreement YAML contains a precomputed comparison, but it cannot be independently verified and is not reported as an aggregation result.
Provided comparison artifact (unverified): {'double_reviewed_n': 208, 'agreements_n': 204, 'disagreements_n': 4, 'raw_agreement': 0.9807692307692307, 'cohen_kappa': 0.0, 'cohen_kappa_note': 'Reviewer A assigned CORRECT to all 208 double-reviewed items, so marginal expected agreement equals observed agreement; kappa is therefore 0 despite 98.08% raw agreement.', 'gwet_ac1': 0.9803958529688972}.

## Adjudication

Accepted the four supplied recommendations as `WRONG`; 4 decisions are written to `adjudication_results.yaml`. The four A labels appear in the disagreement artifact but are absent from the Reviewer-A result files.

- `053d9fe47d105986611506c8` — `Campus Guide` / `forge.change_zone.v1`: Reviewer A `CORRECT`, Reviewer B `WRONG`, final `WRONG`. The sampled Forge occurrence has Origin=Library and Destination=Library. It performs within-library selection or repositioning rather than crossing a zone boundary, so this occurrence does not support zone_transition.
- `80e88eda5a088379b9af218a` — `Knowledge Exploitation` / `forge.change_zone.v1`: Reviewer A `CORRECT`, Reviewer B `WRONG`, final `WRONG`. The sampled Forge occurrence has Origin=Library and Destination=Library. It performs within-library selection or repositioning rather than crossing a zone boundary, so this occurrence does not support zone_transition.
- `23a6562a6e6a5c5879b55310` — `Neera, Wild Mage` / `forge.change_zone_all.v1`: Reviewer A `CORRECT`, Reviewer B `WRONG`, final `WRONG`. The sampled Forge occurrence has Origin=Library and Destination=Library. It performs within-library selection or repositioning rather than crossing a zone boundary, so this occurrence does not support zone_transition.
- `532892f8dc083b10a99ec57d` — `Aetherworks Marvel` / `forge.change_zone_all.v1`: Reviewer A `CORRECT`, Reviewer B `WRONG`, final `WRONG`. The sampled Forge occurrence has Origin=Library and Destination=Library. It performs within-library selection or repositioning rather than crossing a zone boundary, so this occurrence does not support zone_transition.

## Final primary results

Not computed. Expected, if the complete review set validates: 460 total (455 CORRECT, 5 WRONG). Current A input has 300 unique IDs, so no pattern precision or interval is emitted.

## Pattern table

Unavailable until the missing Reviewer-A reviews are supplied and all 208 B IDs are verified as an exact subset.

## Validation findings

The four supplied adjudications identify Forge `ChangeZone` / `ChangeZoneAll` occurrences with `Origin=Library` and `Destination=Library`; those occurrences reposition cards within the library and do not support a zone-boundary transition. The existing XMage unused-import lexical false positive is Reviewer A's `xmage.destroy_target_effect.v1` WRONG result in the supplied unique-ID subset. These findings do not change mappings or extractor behavior.

## Requirement-level status

No Requirement-level precision is calculated or combined. `requirement_evidence_projection.yaml` remains unchanged; source-specific pattern paths and cross corroboration are separate.

## Next-step blockers/findings

- Reviewer A has 300 unique result IDs, expected 460
- Reviewer B has 160 IDs absent from Reviewer A; B must be an exact 208-item subset of A
- The disagreement artifact supplies Reviewer-A labels for 4 IDs absent from the Reviewer-A result files

Supply the missing 160 Reviewer-A primary decisions, including A labels for all 208 B double-review IDs (the current A files are missing 160 of those IDs; four A labels appear only in the disagreement artifact). Then rerun aggregation; the original reviewer files will remain untouched.
