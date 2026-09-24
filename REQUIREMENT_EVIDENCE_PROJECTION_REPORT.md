# Phase 0.2D — Requirement Evidence Projection

## Scope

Extractor `0.2.1`; pinned Scryfall `0ce026779dae1a9a6448ef7a85e606d662343f5e`, Forge `cef86f363d7f7d5b3293248a75f550a7c3404066`, XMage `6212eb37907c1ce751d8a3fea8b3322056dc0264`; mapping SHA-256 `3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a`. Projection identity is the Scryfall `oracle_id`.
This deterministic read model lists current mapped Requirement evidence under extractor 0.2.1. It does not modify extraction or mapping semantics.

## Projection semantics

A card–Requirement pair records active source occurrences and their evidence paths. Forge and XMage remain implementation witnesses, and explicit cross-engine validation patterns remain separate from source corroboration. No evidence means only that no currently extracted mapped evidence was joined to the Oracle identity; it does not mean the real card lacks that capability. `COMPLETENESS_UNVERIFIED` is not a completeness claim.

## Input validation scope

Extractor differential validation: `DIFFERENTIAL_VALIDATION_COMPLETE`. Exact unchanged occurrence identity transfer is bound to `07335ad502e4512712de0af6e4d8cd7fb0322d0a49952fc9826c8cc66b20c36f`. Removed occurrences active in projection: 0; added candidates: 0.

## Card population

Oracle cards: 36,923. Cards with mapped Requirement evidence: 16,301. Cards with no mapped Requirement evidence: 20,622. Cards with unresolved tokens or source warnings: 24,585. 9 historical KEEP_WITH_FLAG join warnings are propagated where their Oracle identities occur.

## Requirement population

Generic Requirement identifiers in the current mappings: 14. Card–Requirement pairs: 21,196. Active mapped source occurrences: 29,182. These use separate counting units.

## Evidence paths

Distinct active source mapping paths: 29. Paths with historical 0.2.0 review metadata: 13; without a selected review record: 16. Active occurrences with exact unchanged identity transfer: 29,182. Historical pattern precision appears only as scoped metadata in each path profile; it is not recalculated under 0.2.1.

## Forge-only evidence

Forge-only card–Requirement pairs: 14,620. Each retains its Forge construct, source record, action-local fields, occurrence identity, join warnings, and validation path metadata where available.

## XMage-only evidence

XMage-only card–Requirement pairs: 750. Each retains its mapped class, source record, executable-use classification, excerpt, join warnings, and validation path metadata where available.

## Cross-engine corroboration

Card–Requirement pairs with both Forge and XMage source evidence: 5,826. Explicit validated cross-engine paths: 2. Source corroboration alone does not imply rules correctness.

## Validated vs unreviewed evidence paths

Reviewed mapping paths display their historical 0.2.0 review scope and the 0.2.1 exact-identity transfer status separately. Mappings without an explicit Phase 0.2B pattern remain `UNREVIEWED`. The projection does not infer validation from a similar pattern name.

## Unresolved evidence

Cards with unresolved evidence: 24,585. Unmapped constructs stay attached to their card identity and source record where known. Exact-unmatched records remain outside card projections rather than being attached by fuzzy name matching. Unmatched source-record counts: Forge 48, XMage 55; ambiguous matching records: 1520.

## Completeness limitations

Lexical extraction cannot prove that all semantics were captured. Cards with no mapped evidence may have no joined implementation record, may have only unmapped evidence, or may use unrecognized constructs. No card is declared fully semantically resolved.

## Why this is not CAP eligibility

The projection is implementation evidence, not Comprehensive Rules truth, card completeness, capability certification, or CAP eligibility. It produces no `CAP_ELIGIBLE` boolean and no Requirement-level combined precision.

## Next phase

Review the projected evidence schema and counts before defining any separate Requirement-to-CAP ontology work. No rules authority, mapping expansion, SQLite, or Manafold integration was added.

Historical candidate occurrence comparison: extractor 0.2.0 had 29,286 mapped occurrences; extractor 0.2.1 has 29,182; difference -104.
