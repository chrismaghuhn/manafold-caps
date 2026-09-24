# Phase 0.2A — Pattern Validation Harness + Review Packet

## Summary

Selected 15 patterns and produced 460 deterministic card-level review samples from 27,896 pattern/source occurrences. Risk classes: LOW 3, MEDIUM 8, HIGH 4.
All inputs use pinned revisions Scryfall `0ce026779dae1a9a6448ef7a85e606d662343f5e`, Forge `cef86f363d7f7d5b3293248a75f550a7c3404066`, XMage `6212eb37907c1ce751d8a3fea8b3322056dc0264`. Extractor `0.2.0`; mapping SHA-256 `3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a`.

No mapping has been validated yet. No precision claim is made yet. No CAP eligibility decision exists.

## Selected patterns

Population is the number of distinct exact-joined Scryfall identities containing the construct (or both constructs for cross patterns). `source_population_records` counts all source records with the construct across the pinned corpus; it is a different unit. Sampling uses only exact-joined identities. The cross-pattern rows are labeled corroboration, not independent semantic validation.

| pattern | why selected | risk | population cards | target n | sampled n | both-engine cards | second review n |
|---|---|---:|---:|---:|---:|---:|---:|
| `forge.draw.v1` | Explicit draw action; useful low-risk baseline for a frequent primitive. | LOW | 2,458 | 20 | 20 | 1,567 | 0 |
| `forge.token.v1` | Explicit token creation action; compare card text with script token parameters. | LOW | 2,230 | 20 | 20 | 1,462 | 0 |
| `xmage.gain_life_effect.v1` | Narrow named effect with a direct gain-life meaning. | LOW | 684 | 20 | 20 | 646 | 0 |
| `forge.deal_damage.v1` | Damage amount, recipient, and distribution can materially change the requirement context. | MEDIUM | 2,070 | 30 | 30 | 1,342 | 6 |
| `forge.destroy.v1` | Inspect target/filter and regeneration-related parameters; the action name alone may be broad. | MEDIUM | 1,205 | 30 | 30 | 810 | 6 |
| `forge.put_counter.v1` | Counter type, quantity, target, and scope may be important omitted context. | MEDIUM | 1,947 | 30 | 30 | 1,279 | 6 |
| `xmage.damage_target_effect.v1` | Named damage effect, but amount and target scope require contextual review. | MEDIUM | 921 | 30 | 30 | 871 | 6 |
| `xmage.destroy_target_effect.v1` | Targeted destroy effect; inspect filters and effect parameters. | MEDIUM | 705 | 30 | 30 | 672 | 6 |
| `xmage.add_counters_source_effect.v1` | Source counter effect; counter kind, amount, and recipient may be broader than the generic candidate. | MEDIUM | 832 | 30 | 30 | 784 | 6 |
| `forge.change_zone.v1` | Origin, destination, selection, cardinality, and object linkage may be collapsed by the generic requirement. | HIGH | 4,136 | 40 | 40 | 2,660 | 40 |
| `forge.change_zone_all.v1` | Mass transitions may differ materially from single-object transitions; inspect filters and cardinality. | HIGH | 467 | 40 | 40 | 302 | 40 |
| `xmage.exile_target_effect.v1` | Exile is a specific destination and targeted effect; test whether zone_transition is too broad. | HIGH | 243 | 40 | 40 | 228 | 40 |
| `xmage.return_to_hand_source_effect.v1` | Return-to-hand has source-object and destination context that may not fit a bare transition label. | HIGH | 117 | 40 | 40 | 115 | 40 |
| `cross.damage.deal_damage__damage_target_effect.v1` | Review cards with both implementation constructs; agreement is corroboration, not independent semantic authority. | MEDIUM | 869 | 30 | 30 | 869 | 6 |
| `cross.create_token.token__create_token_effect.v1` | Review cards with both implementation constructs; agreement does not establish rules correctness. | MEDIUM | 1,196 | 30 | 30 | 1,196 | 6 |

High-risk context to inspect:
- `forge.change_zone.v1`: Origin, Destination, ValidTgts, ValidCards, ChangeType, ChangeNum, Defined, SubAbility.
- `forge.change_zone_all.v1`: Origin, Destination, ValidCards, ChangeType, ChangeNum, selection_mode, cardinality.
- `xmage.exile_target_effect.v1`: target, filter, source_zone, destination_zone.
- `xmage.return_to_hand_source_effect.v1`: source_object, source_zone, destination_zone, owner_or_controller.

## Deterministic sampling

Pattern-specific candidates are deduplicated by Oracle identity. Within each pattern, examples are grouped by card type, single-face/multiface layout, Oracle-text length, and available engine evidence. Within each stratum they are ordered by SHA-256 of stable sample ID; sorted strata are then interleaved round-robin until the target is reached. Sample IDs bind pattern ID, Oracle ID, and pinned source-record identity. Repeated source-row occurrences are reserved after first selection so the same row is not accidentally reviewed twice across this batch. If a pattern's eligible pool is below target, all available cards are included.
The packet contains 460 samples, at most 500. Source occurrence identities are based on global row offsets within the pinned dataset revision; source revision is part of the identity.

## Reviewer protocol

Second review is required for 208 samples: all HIGH-risk items and a deterministic 20% from each MEDIUM-risk pattern (208 marked in the packet). LOW-risk items have no second review in this initial batch.
Each item has empty `review_fields`. `review_results.example.yaml` shows the result format. Give Reviewer B a separate copy containing the selected `second_review_required` items; do not include Reviewer A's result file. Reviewer IDs are opaque labels. No review results were supplied or inferred.

## Retained context

Review items include current Scryfall Oracle text, card type/layout/faces, implementation evidence, and exact join method. Forge evidence retains script action snippets and parsed `$` parameters such as origin, destination, target/filter, cardinality, damage/counter/token values when present. XMage evidence retains prompt fields, imports/classes, and a source excerpt around relevant constructors. Higher-risk zone patterns explicitly list the context fields reviewers should inspect.
All nine Phase 0.1.2 `KEEP_WITH_FLAG` XMage type-line warnings are listed in `pattern_inventory.json`; 1 sampled card carries warning metadata directly in its review item. Join review remains separate from semantic pattern review.

## Validation state

Every pattern is `AWAITING_REVIEW`; `patterns_validated = 0`. Precision estimate and Wilson bounds are null. Inter-rater agreement is `NOT_AVAILABLE`; no Cohen's kappa or Gwet's AC1 value is produced without two real independent result sets.

Proposed Phase 0.2B reporting: accept only `CORRECT` as accepted for a primary precision estimate; show `TOO_BROAD`, `TOO_NARROW`, `CONTEXT_DEPENDENT`, and `WRONG` separately as decisive non-accepts. Keep `AMBIGUOUS` and `SOURCE_EVIDENCE_INSUFFICIENT` out of that decisive denominator and report them separately. Exclude reviewer disagreements from precision until adjudicated; do not count disagreement as an extractor error. Report raw agreement plus an agreement coefficient only after independent reviews exist. Use the Wilson 95% lower bound when interpreting small sample estimates.

## Data quality and blockers

No pinned-source or join-review blocker occurred. The existing suspicious-join review retained 49 stale-wording joins and 9 warning-flagged XMage type-line encoding cases; packet items preserve those warnings. Cross-engine patterns measure whether the proposed generic requirement describes the card-level evidence, not whether either engine is rules-correct.

## Ready for human review

Yes. Review the JSONL packet and return completed result YAML separately per reviewer. Do not edit mappings or treat corroboration as validation in this phase.
