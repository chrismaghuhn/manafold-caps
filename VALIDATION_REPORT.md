# Phase 0.2A.1 — Statistical & Sampling Corrections

## Summary

Primary probability sample: 460 items; forced join-warning audit: 1; total review packet items: 461. The original LOW-risk 60 and all 460 Phase 0.2A probability sample IDs are preserved.
Selected patterns: 15 (LOW 3, MEDIUM 8, HIGH 4); blind second review is assigned to 208 primary probability items.
Pinned source revisions are Scryfall `0ce026779dae1a9a6448ef7a85e606d662343f5e`, Forge `cef86f363d7f7d5b3293248a75f550a7c3404066`, XMage `6212eb37907c1ce751d8a3fea8b3322056dc0264`. Extractor `0.2.0`; mapping SHA-256 `3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a`.

No real review results were consumed. No semantic precision is calculated. No mappings, rules evidence, or CAP eligibility were changed.

## Statistical sampling corrections

Primary probability items remain distinct from forced audit items. `total_samples` and all pattern sample-size/interval calculations refer only to the 460 probability items. The single forced audit item has `selection_basis: FORCED_FLAGGED_JOIN_AUDIT`; it is excluded from every statistical denominator.
The existing 460 probability sample IDs match the captured Phase 0.2A baseline digest `feeb4a19ef205df5cb61078e2df8f1ba11f4570b548ac238bd84f59447e93faf`; the LOW 60 match `7423edb900b12bbd86242937da295ea66833c0b4dbcafce1c643917c260eac31`. Existing Reviewer-A decisions can reuse those IDs.

## Finite population handling

Method selector threshold: sampling fraction <= 5% uses `WILSON_BINOMIAL`; larger fractions use `FINITE_POPULATION_HYPERGEOMETRIC` exact inversion under hypergeometric sampling without replacement. This is a planned method only; accepted counts are null, so no interval estimate or bound is calculated.
Patterns by planned method: Wilson/binomial 12; finite-population hypergeometric 3.

| pattern | N | probability n | sampling fraction | planned interval | forced n |
|---|---:|---:|---:|---|---:|
| `forge.draw.v1` | 2,458 | 20 | 0.00814 | `WILSON_BINOMIAL` | 0 |
| `forge.token.v1` | 2,230 | 20 | 0.00897 | `WILSON_BINOMIAL` | 0 |
| `xmage.gain_life_effect.v1` | 684 | 20 | 0.02924 | `WILSON_BINOMIAL` | 0 |
| `forge.deal_damage.v1` | 2,070 | 30 | 0.01449 | `WILSON_BINOMIAL` | 1 |
| `forge.destroy.v1` | 1,205 | 30 | 0.02490 | `WILSON_BINOMIAL` | 0 |
| `forge.put_counter.v1` | 1,947 | 30 | 0.01541 | `WILSON_BINOMIAL` | 0 |
| `xmage.damage_target_effect.v1` | 921 | 30 | 0.03257 | `WILSON_BINOMIAL` | 0 |
| `xmage.destroy_target_effect.v1` | 705 | 30 | 0.04255 | `WILSON_BINOMIAL` | 0 |
| `xmage.add_counters_source_effect.v1` | 832 | 30 | 0.03606 | `WILSON_BINOMIAL` | 0 |
| `forge.change_zone.v1` | 4,136 | 40 | 0.00967 | `WILSON_BINOMIAL` | 0 |
| `forge.change_zone_all.v1` | 467 | 40 | 0.08565 | `FINITE_POPULATION_HYPERGEOMETRIC` | 0 |
| `xmage.exile_target_effect.v1` | 243 | 40 | 0.16461 | `FINITE_POPULATION_HYPERGEOMETRIC` | 0 |
| `xmage.return_to_hand_source_effect.v1` | 117 | 40 | 0.34188 | `FINITE_POPULATION_HYPERGEOMETRIC` | 0 |
| `cross.damage.deal_damage__damage_target_effect.v1` | 869 | 30 | 0.03452 | `WILSON_BINOMIAL` | 0 |
| `cross.create_token.token__create_token_effect.v1` | 1,196 | 30 | 0.02508 | `WILSON_BINOMIAL` | 0 |

The standard-library hypergeometric interval helper in `src/cap_miner.py` is prepared for later result aggregation. Synthetic tests cover bounds and census collapse. It is not run on absent review data.

## Known warning coverage

Known Phase 0.1.2 warning records: 9. Naturally sampled: 1. Forced audit samples added: 1. Of the warnings relevant to selected patterns, 2 have review coverage. Other warnings remain registered but do not relate to these selected patterns.

| card | relevant selected patterns | coverage | sample ID |
|---|---|---|---|
| `Expedition Skulker` | none | `NOT_RELEVANT_TO_SELECTED_PATTERNS` | `` |
| `Koma's Faithful` | none | `NOT_RELEVANT_TO_SELECTED_PATTERNS` | `` |
| `Wall of Lost Thoughts` | none | `NOT_RELEVANT_TO_SELECTED_PATTERNS` | `` |
| `Wailing Ghoul` | none | `NOT_RELEVANT_TO_SELECTED_PATTERNS` | `` |
| `Faerie Seer` | none | `NOT_RELEVANT_TO_SELECTED_PATTERNS` | `` |
| `Pelakka Wurm` | forge.draw.v1, xmage.gain_life_effect.v1 | `COVERED_BY_PROBABILITY_SAMPLE` | `03c21bde94362c90febaf2aa` |
| `Fanatical Firebrand` | forge.deal_damage.v1, xmage.damage_target_effect.v1, cross.damage.deal_damage__damage_target_effect.v1 | `COVERED_BY_FORCED_AUDIT` | `a5aad239504276dc868b6712` |
| `Kargan Dragonrider` | none | `NOT_RELEVANT_TO_SELECTED_PATTERNS` | `` |
| `Undersea Invader` | none | `NOT_RELEVANT_TO_SELECTED_PATTERNS` | `` |

Forced records carry their reviewed join status/reason and use stable IDs. They are audit coverage, not representative observations. Warnings outside the selected pattern populations stay in the warning register and are not forced into unrelated pattern reviews.

## Oracle text availability

Counts below use exactly the 460 primary probability items; forced audit items are excluded. Source availability is distinct from canonical Scryfall text.
- Pattern-source Oracle text: PRESENT 414; MISSING 46.
- Source-by-engine rows: Forge PRESENT 380, MISSING 69, NOT_AVAILABLE 11; XMage PRESENT 453, MISSING 0, NOT_AVAILABLE 7.
- Canonical parent text available: 398.
- Canonical face text available: 62.
- Canonical parent and face text available: 0.
- Canonical text completely missing: 0.
- Source text missing while canonical face text exists: 42.

| pattern | primary n | source PRESENT | source MISSING | parent text | face text | canonical missing |
|---|---:|---:|---:|---:|---:|---:|
| `cross.create_token.token__create_token_effect.v1` | 30 | 26 | 4 | 26 | 4 | 0 |
| `cross.damage.deal_damage__damage_target_effect.v1` | 30 | 27 | 3 | 28 | 2 | 0 |
| `forge.change_zone.v1` | 40 | 32 | 8 | 32 | 8 | 0 |
| `forge.change_zone_all.v1` | 40 | 36 | 4 | 37 | 3 | 0 |
| `forge.deal_damage.v1` | 30 | 25 | 5 | 25 | 5 | 0 |
| `forge.destroy.v1` | 30 | 26 | 4 | 26 | 4 | 0 |
| `forge.draw.v1` | 20 | 14 | 6 | 16 | 4 | 0 |
| `forge.put_counter.v1` | 30 | 23 | 7 | 23 | 7 | 0 |
| `forge.token.v1` | 20 | 15 | 5 | 15 | 5 | 0 |
| `xmage.add_counters_source_effect.v1` | 30 | 30 | 0 | 27 | 3 | 0 |
| `xmage.damage_target_effect.v1` | 30 | 30 | 0 | 25 | 5 | 0 |
| `xmage.destroy_target_effect.v1` | 30 | 30 | 0 | 27 | 3 | 0 |
| `xmage.exile_target_effect.v1` | 40 | 40 | 0 | 36 | 4 | 0 |
| `xmage.gain_life_effect.v1` | 20 | 20 | 0 | 16 | 4 | 0 |
| `xmage.return_to_hand_source_effect.v1` | 40 | 40 | 0 | 39 | 1 | 0 |

Each review item carries `source_oracle_text_status`, per-engine source statuses, `canonical_oracle_text_status`, and a named `canonical_oracle.faces` array. `source_oracle_text_status: MISSING` does not imply missing canonical support. `rules_evidence` remains `NOT_CHECKED`; Oracle text is not Comprehensive Rules evidence.

## Requirement evidence projection

`requirement_evidence_projection.yaml` lists separate source mapping paths for 5 Requirements. Pattern precision is not averaged, summed, minimized, maximized, or combined. When both engines support a card candidate, retain Forge and XMage path results separately and record the cross pattern as `CROSS_IMPLEMENTATION_CORROBORATION` only.

## Existing review compatibility

`EXISTING_REVIEW_COMPATIBILITY = PRESERVED`. A runtime guard verifies the complete 460-ID digest and the LOW-risk 60-ID digest before writing the packet. Forced audit items are appended separately; probability rows are not regenerated with altered IDs.

## Validation state and next review

No real Reviewer-A decisions were consumed. No real precision or reviewer agreement is available. Pattern statuses remain `AWAITING_REVIEW`; `patterns_validated = 0`; no CAP eligibility decision exists.

Review `data/output/review_samples.jsonl` for probability samples. Review `data/output/forced_audit_samples.jsonl` separately for forced warning audits. Record results in separate reviewer YAML files copied from `review_results.example.yaml`; do not show Reviewer A's answers to Reviewer B. Use only `selection_basis: PROBABILITY_SAMPLE` for later precision inference. Keep forced audit findings separate.

Phase 0.2B should report source-path validation profiles rather than one synthetic Requirement precision. For a future primary estimate, count `CORRECT` as accepted and decisive labels (`TOO_BROAD`, `TOO_NARROW`, `CONTEXT_DEPENDENT`, `WRONG`) as non-accepts; report `AMBIGUOUS`, `SOURCE_EVIDENCE_INSUFFICIENT`, and reviewer disagreement separately. Exclude disagreements until adjudicated. No such aggregation is implemented here.
