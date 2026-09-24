# Final Phase 0.2C.2 — Differential Revalidation

## Scope

Extractor `0.2.1`, parent `0.2.0`; source revisions: Scryfall `0ce026779dae1a9a6448ef7a85e606d662343f5e`, Forge `cef86f363d7f7d5b3293248a75f550a7c3404066`, XMage `6212eb37907c1ce751d8a3fea8b3322056dc0264`. Mapping SHA-256 `3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a`.
This finalizes only differential removal validation and exact unchanged-candidate transfer. No extractor or mapping behavior was changed.

## Review coverage

Reviewer A: 104 / 104. Reviewer B: 104 / 104. Shared IDs: 104 / 104; both sets exactly match the differential packet.

## Reviewer agreement

Exact agreement: 104 / 104. Disagreements: 0. Both reviewers used a single decision category, so chance-corrected kappa/AC1 are not reported as informative.

## Changed population result

104 / 104 changed evidence removals were independently reviewed by both reviewers and accepted. REMOVAL_WRONG=0, AMBIGUOUS=0, SOURCE_EVIDENCE_INSUFFICIENT=0. Added candidates: 0. This is a census; no Wilson or hypergeometric interval is calculated.

## Forge guard result

98 Forge same-zone removals were accepted by both reviewers. The guard removes only the individual same-zone action occurrence; co-located cross-zone actions remain intact.

## XMage guard result

6 XMage import-only removals were accepted by both reviewers. Genuine executable uses remain evidence; mapped class references confined to non-executable contexts do not.

## Unchanged identity proof

Old unchanged set equals new unchanged set: **True**. Digest: `07335ad502e4512712de0af6e4d8cd7fb0322d0a49952fc9826c8cc66b20c36f`. Added candidate count remains zero.

## Validation transfer

Parent evidence transfers only for exact unchanged candidate occurrence identities. Removed identities have exhaustive two-review validation. Added identities are zero. Per-pattern populations are classified below; historical 0.2.0 estimates are retained without recomputation.

| pattern | parent population | 0.2.1 population | removed Oracle IDs | removed evidence occurrences | status |
|---|---:|---:|---:|---:|---|
| `forge.draw.v1` | 2458 | 2458 | 0 | 0 | UNCHANGED |
| `forge.token.v1` | 2230 | 2230 | 0 | 0 | UNCHANGED |
| `xmage.gain_life_effect.v1` | 684 | 684 | 0 | 0 | UNCHANGED |
| `forge.deal_damage.v1` | 2070 | 2070 | 0 | 0 | UNCHANGED |
| `forge.destroy.v1` | 1205 | 1205 | 0 | 0 | UNCHANGED |
| `forge.put_counter.v1` | 1947 | 1947 | 0 | 0 | UNCHANGED |
| `xmage.damage_target_effect.v1` | 921 | 921 | 0 | 0 | UNCHANGED |
| `xmage.destroy_target_effect.v1` | 705 | 704 | 1 | 1 | REMOVALS_ONLY |
| `xmage.add_counters_source_effect.v1` | 832 | 832 | 0 | 0 | UNCHANGED |
| `forge.change_zone.v1` | 4136 | 4088 | 48 | 80 | REMOVALS_ONLY |
| `forge.change_zone_all.v1` | 467 | 457 | 10 | 18 | REMOVALS_ONLY |
| `xmage.exile_target_effect.v1` | 243 | 242 | 1 | 1 | REMOVALS_ONLY |
| `xmage.return_to_hand_source_effect.v1` | 117 | 116 | 1 | 1 | REMOVALS_ONLY |
| `cross.damage.deal_damage__damage_target_effect.v1` | 869 | 869 | 0 | 0 | UNCHANGED |
| `cross.create_token.token__create_token_effect.v1` | 1196 | 1195 | 1 | 1 | REMOVALS_ONLY |

## Historical 0.2.0 validation relationship

Phase 0.2B remains historical evidence under extractor 0.2.0: 460 primary samples, 455 final CORRECT, 5 final WRONG. No original validation files were overwritten. No confidence intervals were recalculated or automatically assigned to extractor 0.2.1.

## Limitations

Differential completion means only that the two guards' complete changed occurrence population was accepted and exact unchanged occurrence identities can inherit their parent evidence. It is not CAP eligibility, a Comprehensive Rules validation, a global semantic-completeness claim, or numerical Requirement-level precision.

## Readiness for Phase 0.2D

READY. The extractor 0.2.1 differential is complete: 98 Forge same-zone and 6 XMage import-only removals accepted by both reviewers, 0 disagreements, 0 additions, and the unchanged identity digest preserved. Phase 0.2D may proceed as separate work.
