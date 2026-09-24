# Phase 0.2C.2 — Extractor 0.2.1 Differential Revalidation Packet

## Scope

Extractor 0.2.1, parent 0.2.0. Pinned sources: Scryfall `0ce026779dae1a9a6448ef7a85e606d662343f5e`, Forge `cef86f363d7f7d5b3293248a75f550a7c3404066`, XMage `6212eb37907c1ce751d8a3fea8b3322056dc0264`. Mapping SHA-256 `3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a`.
This phase generates an exhaustive blind review packet for the 0.2.0 → 0.2.1 removed evidence set. It does not change extraction or review decisions.

## Parent validation

Parent validation remains tied to extractor 0.2.0, review batch `phase-0.2a-batch-1`: 460 primary samples, 455 final CORRECT, and 5 final WRONG. Historical labels and intervals are unchanged.

## Changed occurrence population

Removed evidence occurrences: 104; added: 0. Full changed population is covered (sampling fraction 1.0). Guard split: Forge same-zone 98, XMage non-executable import-only 6. Because this is a census of all changed occurrences, no Wilson or hypergeometric interval applies; if all removals are accepted the result is reported as 104/104 reviewed and accepted, not sampled precision.

## Forge removals

All 98 Forge items identify the exact action type and per-token action occurrence, action-local parameters, raw action line, and sibling action lines from that record. Review asks whether suppressing that one occurrence is correct.

## XMage removals

All 6 XMage items contain the mapped class's import lines, every source reference with context and line number, the executable-context excerpt, canonical card text, and full source Java. Review asks whether the non-executable-only evidence is correctly suppressed.

## Review packet

`data/output/differential_review_samples.jsonl` contains 104 unique items: Reviewer A required on all 104, Reviewer B required blind on all 104. Decisions are blank. Allowed labels are `REMOVAL_CORRECT`, `REMOVAL_WRONG`, `AMBIGUOUS`, and `SOURCE_EVIDENCE_INSUFFICIENT`.

## Unchanged candidate identity proof

Recomputed unchanged-set digest: `07335ad502e4512712de0af6e4d8cd7fb0322d0a49952fc9826c8cc66b20c36f`. It matches the Phase 0.2C.1 old and new unchanged-set digest. The unchanged candidate identity set is eligible for later validation transfer only by exact occurrence identity.

## Validation-transfer rule

Transfer Phase 0.2B evidence only for occurrence identities proven unchanged. Removed occurrences require this differential review; card name, Requirement, or pattern-name similarity alone is not enough. 0.2.1 added no candidates, so the new-candidate validation population is zero.

## Why full 460-sample re-review is unnecessary

The 455 previously accepted sample paths remain unchanged, the complete unchanged candidate identity set has the same digest in old/new sets, and extractor 0.2.1 adds no candidate occurrences. The validation delta is the exact set of 104 removed occurrences. This does not transfer 0.2.0 confidence intervals to 0.2.1.

## Conditions for extractor 0.2.1 validation

All 104 removals must be reviewed by both blind reviewers; all disagreements must be adjudicated; no unresolved wrong-removal or ambiguous guard issue may remain; unchanged-set identity proof must still match; and added candidates must remain zero. Any `REMOVAL_WRONG` means the corresponding guard is not fully validated and the affected 0.2.1 evidence cannot receive clean transferred validation.

## Next human-review step

Give `differential_review_results.example.yaml` as the format template. Export the canonical JSONL packet to Reviewer A and Reviewer B separately; do not expose A's result file to B. Record decisions in separate YAML files using the stable `differential_sample_id`. No review answers, agreement statistics, precision, or eligibility decisions are present yet.
