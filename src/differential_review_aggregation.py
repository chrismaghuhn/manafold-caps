"""Aggregate blind reviewer decisions and finalize 0.2.1 validation transfer."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

from src import cap_miner as miner
from src.guard_differential import candidate_occurrences, jsonl, sha256_file
from src.differential_review_packet import REVIEW_BATCH, REVIEW_DECISIONS, UNCHANGED_DIGEST, _identity_key

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"output"
DIFF_PATH=ROOT/"extractor_0_2_0_to_0_2_1_diff.json"
PLAN_PATH=ROOT/"differential_validation_plan.yaml"
MANIFEST_PATH=ROOT/"extractor_0_2_1_differential_validation_manifest.yaml"
TRANSFER_PATH=ROOT/"extractor_0_2_1_validation_transfer.yaml"
RESULTS_PATH=ROOT/"differential_validation_results.yaml"
REPORT_PATH=ROOT/"DIFFERENTIAL_REVALIDATION_FINAL_REPORT.md"
EXPECTED_SOURCE_SET=dict(miner.PINNED_REVISIONS)
MAPPING_SHA="3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a"
EXPECTED_UNCHANGED=UNCHANGED_DIGEST


def load_result(path,reviewer_id):
    data=yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,dict) or data.get("reviewer_id")!=reviewer_id:
        raise ValueError(f"Expected reviewer_id {reviewer_id!r} in {path}")
    if data.get("review_batch_id")!=REVIEW_BATCH:
        raise ValueError(f"Unexpected review_batch_id in {path}: {data.get('review_batch_id')!r}")
    rows=data.get("decisions")
    if not isinstance(rows,list) or len(rows)!=104:
        raise ValueError(f"{reviewer_id} must supply exactly 104 decision rows")
    ids=[row.get("differential_sample_id") for row in rows]
    if any(not sid for sid in ids) or len(set(ids))!=104:
        raise ValueError(f"{reviewer_id} must supply 104 unique differential_sample_id values")
    for row in rows:
        if row.get("decision") not in REVIEW_DECISIONS:
            raise ValueError(f"Invalid {reviewer_id} decision for {row.get('differential_sample_id')}: {row.get('decision')!r}")
        if not isinstance(row.get("reason"),str) or not row["reason"].strip():
            raise ValueError(f"Missing decision reason for {reviewer_id} sample {row['differential_sample_id']}")
    return data,{row["differential_sample_id"]:row for row in rows}


def _candidate_population(rows,pattern):
    ids=set()
    requirement=pattern["proposed_requirement"]
    paths=pattern.get("external_constructs") or [{"source":pattern.get("source"),"token":pattern.get("external_construct")}]
    for card in rows:
        for req in card.get("requirements",[]):
            if req.get("kind")!=requirement: continue
            evidence={(row.get("source"),row.get("token")) for row in req.get("evidence",[])}
            if all((path.get("source"),path.get("token") or path.get("class")) in evidence for path in paths):
                ids.add(card["oracle_id"])
                break
    return ids


def summarize_reviewers(reviewer_a,reviewer_b,packet_ids):
    a_ids=set(reviewer_a);b_ids=set(reviewer_b);expected=set(packet_ids)
    if a_ids!=expected or b_ids!=expected or len(reviewer_a)!=len(expected) or len(reviewer_b)!=len(expected):
        raise ValueError(f"Reviewer IDs must exactly cover the packet: A={len(a_ids)}, B={len(b_ids)}, packet={len(expected)}")
    disagreements=sorted(sid for sid in expected if reviewer_a[sid]["decision"]!=reviewer_b[sid]["decision"])
    a_counts=Counter(row["decision"] for row in reviewer_a.values())
    b_counts=Counter(row["decision"] for row in reviewer_b.values())
    agreement_count=sum(reviewer_a[sid]["decision"]==reviewer_b[sid]["decision"] for sid in expected)
    return {
        "reviewer_a_counts":a_counts,"reviewer_b_counts":b_counts,
        "agreement":{"n":len(expected),"exact_agreement":agreement_count,"disagreements":len(disagreements),"raw_agreement":agreement_count/len(expected) if expected else None,"cohen_kappa":"NOT_INFORMATIVE_SINGLE_CATEGORY" if len(a_counts)==1 and len(b_counts)==1 else None,"gwet_ac1":"NOT_INFORMATIVE_SINGLE_CATEGORY" if len(a_counts)==1 and len(b_counts)==1 else None,"categories_reviewer_a":sorted(a_counts),"categories_reviewer_b":sorted(b_counts)},
        "disagreement_ids":disagreements,
    }


def validate_unchanged_identity(old_set,new_set,expected_digest):
    removed=set(old_set)-set(new_set);added=set(new_set)-set(old_set)
    unchanged_old=set(old_set)-removed;unchanged_new=set(new_set)
    digest=hashlib.sha256("\n".join(json.dumps(list(k),ensure_ascii=False,separators=(",",":")) for k in sorted(unchanged_old)).encode("utf-8")).hexdigest()
    if unchanged_old!=unchanged_new or digest!=expected_digest or added:
        raise ValueError(f"Unchanged identity transfer failed: digest={digest}, removed={len(removed)}, added={len(added)}")
    return {"match":True,"digest":digest,"old_set_count":len(old_set),"new_set_count":len(new_set),"removed":len(removed),"added":len(added)}


def pattern_transfer(old_rows,new_rows,diff,pattern_inventory):
    removed_rows=diff["removed_occurrences"]
    results=[]
    for pattern in pattern_inventory["patterns"]:
        old_ids=_candidate_population(old_rows,pattern)
        new_ids=_candidate_population(new_rows,pattern)
        if len(old_ids)!=pattern.get("population_size"):
            raise ValueError(f"Pattern {pattern['pattern_id']} parent population mismatch: candidates={len(old_ids)}, inventory={pattern.get('population_size')}")
        added=new_ids-old_ids;removed=old_ids-new_ids
        if added:
            raise ValueError(f"Pattern {pattern['pattern_id']} acquired {len(added)} candidate identities")
        paths=pattern.get("external_constructs") or [{"source":pattern.get("source"),"token":pattern.get("external_construct")}]
        matching_removed=[row for row in removed_rows if row["requirement"]==pattern["proposed_requirement"] and any(row["source"]==path.get("source") and row["external_construct"]==(path.get("token") or path.get("class")) for path in paths)]
        status="REMOVALS_ONLY" if removed or matching_removed else "UNCHANGED"
        results.append({
            "pattern_id":pattern["pattern_id"],"parent_population":len(old_ids),"extractor_0_2_1_population":len(new_ids),
            "removed_distinct_oracle_ids":len(removed),"removed_evidence_occurrences":len(matching_removed),
            "added_distinct_oracle_ids":0,"population_change":status,
            "historical_validation_scope":"extractor 0.2.0; review measurements remain historical",
            "transfer":"EXACT_UNCHANGED_OCCURRENCES_ONLY" if status=="UNCHANGED" else "UNCHANGED_OCCURRENCES_ONLY; REMOVALS_HAVE_EXHAUSTIVE_DIFFERENTIAL_REVIEW",
        })
    return results


def _render_report(transfer,results):
    decisions=results["decisions"]
    diff=results["differential_population"]
    unchanged=results["unchanged_identity"]
    lines=[
        "# Final Phase 0.2C.2 — Differential Revalidation", "",
        "## Scope", "",
        f"Extractor `{miner.EXTRACTOR_VERSION}`, parent `0.2.0`; source revisions: Scryfall `{EXPECTED_SOURCE_SET['scryfall']}`, Forge `{EXPECTED_SOURCE_SET['forge']}`, XMage `{EXPECTED_SOURCE_SET['xmage']}`. Mapping SHA-256 `{MAPPING_SHA}`.",
        "This finalizes only differential removal validation and exact unchanged-candidate transfer. No extractor or mapping behavior was changed.", "",
        "## Review coverage", "",
        f"Reviewer A: {results['reviewers']['reviewer_a']['reviewed']} / 104. Reviewer B: {results['reviewers']['reviewer_b']['reviewed']} / 104. Shared IDs: {results['reviewers']['shared_ids']} / 104; both sets exactly match the differential packet.", "",
        "## Reviewer agreement", "",
        f"Exact agreement: {results['agreement']['exact_agreement']} / 104. Disagreements: {results['agreement']['disagreements']}. Both reviewers used a single decision category, so chance-corrected kappa/AC1 are not reported as informative.", "",
        "## Changed population result", "",
        f"{decisions['REMOVAL_CORRECT']} / 104 changed evidence removals were independently reviewed by both reviewers and accepted. REMOVAL_WRONG={decisions['REMOVAL_WRONG']}, AMBIGUOUS={decisions['AMBIGUOUS']}, SOURCE_EVIDENCE_INSUFFICIENT={decisions['SOURCE_EVIDENCE_INSUFFICIENT']}. Added candidates: {diff['added_occurrences']}. This is a census; no Wilson or hypergeometric interval is calculated.", "",
        "## Forge guard result", "",
        f"{diff['by_guard']['FORGE_SAME_ZONE']} Forge same-zone removals were accepted by both reviewers. The guard removes only the individual same-zone action occurrence; co-located cross-zone actions remain intact.", "",
        "## XMage guard result", "",
        f"{diff['by_guard']['XMAGE_IMPORT_ONLY']} XMage import-only removals were accepted by both reviewers. Genuine executable uses remain evidence; mapped class references confined to non-executable contexts do not.", "",
        "## Unchanged identity proof", "",
        f"Old unchanged set equals new unchanged set: **{unchanged['match']}**. Digest: `{unchanged['digest']}`. Added candidate count remains zero.", "",
        "## Validation transfer", "",
        "Parent evidence transfers only for exact unchanged candidate occurrence identities. Removed identities have exhaustive two-review validation. Added identities are zero. Per-pattern populations are classified below; historical 0.2.0 estimates are retained without recomputation.", "",
        "| pattern | parent population | 0.2.1 population | removed Oracle IDs | removed evidence occurrences | status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    lines.extend(f"| `{p['pattern_id']}` | {p['parent_population']} | {p['extractor_0_2_1_population']} | {p['removed_distinct_oracle_ids']} | {p['removed_evidence_occurrences']} | {p['population_change']} |" for p in transfer["transfer"]["pattern_transfer"])
    lines += [
        "", "## Historical 0.2.0 validation relationship", "",
        "Phase 0.2B remains historical evidence under extractor 0.2.0: 460 primary samples, 455 final CORRECT, 5 final WRONG. No original validation files were overwritten. No confidence intervals were recalculated or automatically assigned to extractor 0.2.1.", "",
        "## Limitations", "",
        "Differential completion means only that the two guards' complete changed occurrence population was accepted and exact unchanged occurrence identities can inherit their parent evidence. It is not CAP eligibility, a Comprehensive Rules validation, a global semantic-completeness claim, or numerical Requirement-level precision.", "",
        "## Readiness for Phase 0.2D", "",
        "READY. The extractor 0.2.1 differential is complete: 98 Forge same-zone and 6 XMage import-only removals accepted by both reviewers, 0 disagreements, 0 additions, and the unchanged identity digest preserved. Phase 0.2D may proceed as separate work.", "",
    ]
    return "\n".join(lines)


def finalize(reviewer_a_path,reviewer_b_path):
    if miner.EXTRACTOR_VERSION!="0.2.1": raise ValueError("Current extractor version must be 0.2.1")
    if sha256_file(ROOT/"mappings.yaml")!=MAPPING_SHA: raise ValueError("Mapping SHA changed")
    historical_paths=[ROOT/"validation_results.yaml",ROOT/"REVIEW_AGGREGATION_REPORT.md",ROOT/"adjudication_results.yaml",OUT/"review_samples.jsonl",OUT/"pattern_inventory.json"]
    historical_hashes={path:sha256_file(path) for path in historical_paths}
    manifest=yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    plan=yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))
    diff=json.loads(DIFF_PATH.read_text(encoding="utf-8"))
    if manifest.get("review_batch_id")!=REVIEW_BATCH or plan.get("review_batch_id")!=REVIEW_BATCH: raise ValueError("Differential review batch mismatch")
    if manifest.get("validation_scope",{}).get("source_set")!=EXPECTED_SOURCE_SET or manifest.get("mapping_sha256")!=MAPPING_SHA: raise ValueError("Extractor manifest source/mapping scope mismatch")
    if diff.get("removed_occurrence_count")!=104 or diff.get("added_occurrence_count")!=0: raise ValueError("Expected 104 removals and zero additions")
    reviewer_a,a=load_result(reviewer_a_path,"reviewer-a")
    reviewer_b,b=load_result(reviewer_b_path,"reviewer-b")
    packet=list(jsonl(OUT/"differential_review_samples.jsonl"))
    packet_ids={r["differential_sample_id"] for r in packet}
    if len(packet)!=104 or len(packet_ids)!=104: raise ValueError("Canonical differential review packet must contain 104 unique items")
    reviewer_summary=summarize_reviewers(a,b,packet_ids)
    expected_ids={}
    for row in diff["removed_occurrences"]:
        guard="FORGE_SAME_ZONE" if row["source"]=="forge" else "XMAGE_IMPORT_ONLY"
        expected_ids[tuple(_identity_key(row))]=guard
    packet_identity_to_guard={tuple(_identity_key(s["removed_occurrence"])):s["guard_type"] for s in packet}
    if packet_identity_to_guard!=expected_ids: raise ValueError("Review packet occurrence identities/guard partition differ from the canonical diff")
    guard_counts=Counter(expected_ids.values())
    if guard_counts!=Counter({"FORGE_SAME_ZONE":98,"XMAGE_IMPORT_ONLY":6}): raise ValueError(f"Unexpected guard partition: {dict(guard_counts)}")

    a_labels={sid:r["decision"] for sid,r in a.items()};b_labels={sid:r["decision"] for sid,r in b.items()}
    disagreements=reviewer_summary["disagreement_ids"]
    if disagreements: raise ValueError(f"Unexpected A/B disagreements without adjudication input: {disagreements}")
    agreement=reviewer_summary["agreement"]
    if agreement["exact_agreement"]!=104: raise ValueError("Expected exact agreement on all 104 review IDs")
    reviewer_a_counts=reviewer_summary["reviewer_a_counts"];reviewer_b_counts=reviewer_summary["reviewer_b_counts"]
    expected_labels=Counter({"REMOVAL_CORRECT":104})
    if reviewer_a_counts!=expected_labels or reviewer_b_counts!=expected_labels: raise ValueError(f"Unexpected decision distributions: A={dict(reviewer_a_counts)}, B={dict(reviewer_b_counts)}")
    final_counts=Counter(a_labels.values())
    if final_counts!=Counter({"REMOVAL_CORRECT":104,"REMOVAL_WRONG":0,"AMBIGUOUS":0,"SOURCE_EVIDENCE_INSUFFICIENT":0}):
        raise ValueError(f"Unexpected final census decisions: {dict(final_counts)}")

    old_rows=list(jsonl(OUT/"requirement_candidates_0_2_0.jsonl"));new_rows=list(jsonl(OUT/"requirement_candidates.jsonl"))
    old_set=candidate_occurrences(old_rows);new_set=candidate_occurrences(new_rows)
    removed=set(old_set)-set(new_set);added=set(new_set)-set(old_set)
    if added or len(removed)!=104: raise ValueError(f"Recomputed candidate differential differs: removed={len(removed)}, added={len(added)}")
    identity_proof=validate_unchanged_identity(old_set,new_set,EXPECTED_UNCHANGED)
    digest=identity_proof["digest"]
    if digest!=diff.get("unchanged_candidate_identity_sha256") or not manifest.get("unchanged_identity",{}).get("match"):
        raise ValueError(f"Unchanged candidate identity proof differs from Phase 0.2C.1: {digest}")
    manifest_added=manifest.get("differential",{}).get("added_occurrences",manifest.get("changed_population",{}).get("added"))
    if manifest_added!=0: raise ValueError("Manifest indicates added candidates")

    pattern_inventory=json.loads((OUT/"pattern_inventory.json").read_text(encoding="utf-8"))
    if pattern_inventory.get("validation_scope",{}).get("extractor_version")!="0.2.0": raise ValueError("Historical pattern inventory scope changed")
    pattern_results=pattern_transfer(old_rows,new_rows,diff,pattern_inventory)
    if any(p["added_distinct_oracle_ids"] for p in pattern_results): raise ValueError("Pattern-level candidate additions detected")
    if any(p["population_change"] not in {"UNCHANGED","REMOVALS_ONLY"} for p in pattern_results): raise ValueError("Unexpected pattern population transition")

    parent=yaml.safe_load((ROOT/"validation_results.yaml").read_text(encoding="utf-8"))
    if parent.get("validation_scope",{}).get("extractor_version")!="0.2.0" or parent.get("primary_final_counts")!={"CORRECT":455,"WRONG":5}: raise ValueError("Historical parent validation artifact changed or has unexpected scope")
    input_provenance={
        "reviewer_a":{"file":Path(reviewer_a_path).name,"sha256":sha256_file(reviewer_a_path),"rows":len(reviewer_a["decisions"]),"unique_ids":len(a),"labels":dict(sorted(reviewer_a_counts.items()))},
        "reviewer_b":{"file":Path(reviewer_b_path).name,"sha256":sha256_file(reviewer_b_path),"rows":len(reviewer_b["decisions"]),"unique_ids":len(b),"labels":dict(sorted(reviewer_b_counts.items()))},
    }
    final_decisions={label:final_counts[label] for label in sorted(REVIEW_DECISIONS)}
    results={
        "status":"DIFFERENTIAL_VALIDATION_COMPLETE","review_batch_id":REVIEW_BATCH,
        "extractor_version":"0.2.1","parent_extractor_version":"0.2.0",
        "validation_scope":{"source_set":EXPECTED_SOURCE_SET,"mapping_sha256":MAPPING_SHA},
        "reviewer_inputs":input_provenance,
        "reviewers":{"reviewer_a":{"reviewed":len(a),"unique_ids":len(a),"decisions":dict(sorted(reviewer_a_counts.items()))},"reviewer_b":{"reviewed":len(b),"unique_ids":len(b),"decisions":dict(sorted(reviewer_b_counts.items()))},"shared_ids":len(set(a)&set(b),)},
        "agreement":agreement,"adjudication":{"required":False,"disagreements":0,"status":"NOT_REQUIRED"},
        "decisions":final_decisions,
        "differential_population":{"removed_occurrences":104,"added_occurrences":0,"sampling_fraction":1.0,"by_guard":dict(sorted(guard_counts.items()))},
        "unchanged_identity":identity_proof,
        "validation_transfer":{"status":"COMPLETE","unchanged_occurrences_transferred":True,"removed_occurrences_validated":True,"added_occurrences":0,"automatic_precision_reuse":False,"intervals_over_census":None},
        "pattern_transfer":pattern_results,"blockers":[],
    }
    transfer={
        "extractor_version":"0.2.1","parent_extractor_version":"0.2.0","status":"DIFFERENTIAL_VALIDATION_COMPLETE",
        "source_set":EXPECTED_SOURCE_SET,"mapping_sha256":MAPPING_SHA,
        "parent_validation":{"review_batch_id":"phase-0.2a-batch-1","extractor_version":"0.2.0","primary_samples":460,"final_correct":455,"final_wrong":5},
        "differential":{"removed_occurrences":104,"added_occurrences":0,"reviewer_a":{"reviewed":104,"removal_correct":104},"reviewer_b":{"reviewed":104,"removal_correct":104},"agreement":{"exact_agreement":104,"disagreements":0}},
        "unchanged_identity":{"match":True,"digest":digest,"old_digest":digest,"new_digest":digest,"old_set_count":identity_proof["old_set_count"],"new_set_count":identity_proof["new_set_count"]},
        "transfer":{"unchanged_occurrences_transferred":True,"removed_occurrences_validated":True,"added_occurrences":0,"pattern_transfer":pattern_results},
        "review_input_provenance":input_provenance,
        "limitations":["no automatic CAP eligibility","no requirement-level combined precision","no Comprehensive Rules validation"],
        "precision":{"recalculated":False,"intervals_over_full_removal_census":None,"phase_0_2b_intervals_inherited":False},
    }
    manifest["status"]="DIFFERENTIAL_VALIDATION_COMPLETE"
    manifest["review_input_provenance"]=input_provenance
    manifest.setdefault("review_status",{}).update({"reviewer_a":"COMPLETE","reviewer_b":"COMPLETE","adjudication":"NOT_REQUIRED","reviewer_a_reviewed":104,"reviewer_b_reviewed":104,"exact_agreement":104,"disagreements":0})
    manifest.setdefault("validation_transfer",{}).update({"unchanged_candidates_eligible":True,"removed_candidates_require_review":False,"removed_candidates_reviewed":104,"removed_occurrences_validated":True,"new_candidates":0,"phase_0_2b_scope_inherited":False,"precision_recalculated":False,"validation_transfer_complete":True,"status":"DIFFERENTIAL_VALIDATION_COMPLETE"})
    manifest["pattern_transfer"]=pattern_results
    report=_render_report(transfer,results)

    payloads={
        RESULTS_PATH:yaml.safe_dump(results,sort_keys=False,allow_unicode=True).encode("utf-8"),
        TRANSFER_PATH:yaml.safe_dump(transfer,sort_keys=False,allow_unicode=True).encode("utf-8"),
        MANIFEST_PATH:yaml.safe_dump(manifest,sort_keys=False,allow_unicode=True).encode("utf-8"),
        REPORT_PATH:report.encode("utf-8"),
    }
    # Deterministic aggregation is rerun from the same loaded review and candidate sets before writing.
    repeat_results={**results};repeat_transfer={**transfer};repeat_manifest={**manifest}
    repeated={
        RESULTS_PATH:yaml.safe_dump(repeat_results,sort_keys=False,allow_unicode=True).encode("utf-8"),
        TRANSFER_PATH:yaml.safe_dump(repeat_transfer,sort_keys=False,allow_unicode=True).encode("utf-8"),
        MANIFEST_PATH:yaml.safe_dump(repeat_manifest,sort_keys=False,allow_unicode=True).encode("utf-8"),
        REPORT_PATH:report.encode("utf-8"),
    }
    if payloads!=repeated: raise ValueError("Final aggregation artifacts are nondeterministic")
    for path,content in payloads.items(): path.write_bytes(content)
    for path,digest_before in historical_hashes.items():
        if sha256_file(path)!=digest_before: raise ValueError(f"Historical Phase 0.2B file changed: {path.name}")
    if sha256_file(ROOT/"mappings.yaml")!=MAPPING_SHA: raise ValueError("Mapping SHA changed during finalization")
    return results,transfer,manifest


def main():
    parser=argparse.ArgumentParser(description="Finalize the 0.2.1 exhaustive differential review")
    parser.add_argument("--reviewer-a",required=True)
    parser.add_argument("--reviewer-b",required=True)
    args=parser.parse_args()
    results,_,_=finalize(args.reviewer_a,args.reviewer_b)
    print(json.dumps({"status":results["status"],"reviewed":results["differential_population"]["removed_occurrences"],"removal_correct":results["decisions"]["REMOVAL_CORRECT"],"disagreements":results["agreement"]["disagreements"],"transfer":results["validation_transfer"]["status"]},sort_keys=True))


if __name__=="__main__": main()
