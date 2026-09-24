"""Pinned Phase 0.2C.1 rebuild, guard verification, and 0.2.0/0.2.1 diff."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from src import cap_miner as miner

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"output"
BASELINE_CANDIDATES=OUT/"requirement_candidates_0_2_0.jsonl"
SOURCE_SET={
    "scryfall":"0ce026779dae1a9a6448ef7a85e606d662343f5e",
    "forge":"cef86f363d7f7d5b3293248a75f550a7c3404066",
    "xmage":"6212eb37907c1ce751d8a3fea8b3322056dc0264",
}
MAPPING_SHA="3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a"
KNOWN_FORGE_SAMPLE_IDS={
    "053d9fe47d105986611506c8","80e88eda5a088379b9af218a",
    "23a6562a6e6a5c5879b55310","532892f8dc083b10a99ec57d",
}
KNOWN_XMAGE_SAMPLE_ID="9e58403cc3d80c14b4c5a14c"
HISTORICAL_FILES=(
    "adjudication_results.yaml","validation_results.yaml","REVIEW_AGGREGATION_REPORT.md",
    "review_results.example.yaml",
)
HISTORICAL_OUTPUTS=("review_samples.jsonl","forced_audit_samples.jsonl","pattern_inventory.json")
JOIN_OUTPUTS=("join_audit_stats.json","suspicious_join_audit.json","oracle_mismatch_audit.json")


def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()


def jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)


def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def _source_identity(source,record_index):
    return miner.reviewable_record_identity(source,SOURCE_SET[source],record_index)


def candidate_occurrences(candidate_rows,old_format=False):
    """Canonical identity for each card/source/construct/requirement occurrence."""
    result={}
    for card in candidate_rows:
        oracle_id=card.get("oracle_id")
        per_record_token=Counter()
        for requirement in card.get("requirements",[]):
            kind=requirement["kind"]
            for evidence in requirement.get("evidence",[]):
                source=evidence["source"]
                record_index=evidence.get("source_record_index")
                if record_index is None:
                    raise ValueError(f"Evidence lacks stable source_record_index: {card.get('name')} {evidence}")
                record_identity=_source_identity(source,record_index)
                token=evidence["token"]
                occurrence_index=evidence.get("occurrence_index")
                if occurrence_index is None:
                    occurrence_index=per_record_token[(source,record_index,token)]
                per_record_token[(source,record_index,token)]=max(per_record_token[(source,record_index,token)],occurrence_index+1)
                key=(str(oracle_id),source,record_identity,token,kind,int(occurrence_index))
                if key in result: raise ValueError(f"Duplicate mapped candidate occurrence identity {key}")
                result[key]={"oracle_id":oracle_id,"card_name":card.get("name"),"source":source,"source_record_identity":record_identity,"external_construct":token,"requirement":kind,"occurrence_index":int(occurrence_index)}
    return result


def _digest(keys):
    payload="\n".join(json.dumps(list(key),ensure_ascii=False,separators=(",",":")) for key in sorted(keys))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _review_state(reviewer_a_path):
    data=yaml.safe_load(Path(reviewer_a_path).read_text(encoding="utf-8"))
    rows=data.get("decisions",[])
    if data.get("reviewer_id")!="reviewer-a" or len(rows)!=460 or len({r["sample_id"] for r in rows})!=460:
        raise ValueError("Reviewer-A input must contain exactly 460 unique primary sample IDs")
    labels={r["sample_id"]:r["decision"] for r in rows}
    adjudications=yaml.safe_load((ROOT/"adjudication_results.yaml").read_text(encoding="utf-8"))["decisions"]
    labels.update({r["sample_id"]:r["final_label"] for r in adjudications})
    counts=Counter(labels.values())
    if counts!=Counter({"CORRECT":455,"WRONG":5}):
        raise ValueError(f"Unexpected adjudicated primary labels: {dict(counts)}")
    return labels


def _sample_candidate_groups(sample):
    pattern=sample["pattern"]
    requirement=pattern["proposed_requirement"]
    paths=[]
    if pattern.get("source") in {"forge","xmage"} and pattern.get("external_construct"):
        paths.append((pattern["source"],pattern["external_construct"],requirement))
    for path in pattern.get("external_constructs") or []:
        source=path.get("source");token=path.get("token") or path.get("class")
        if source in {"forge","xmage"} and token: paths.append((source,token,requirement))
    groups=[]
    for source,token,kind in paths:
        evidence=sample.get("evidence",{}).get(source,{})
        record_identity=evidence.get("source_record_identity")
        if record_identity:
            groups.append((str(sample["card"].get("oracle_id")),source,record_identity,token,kind))
    return groups


def reviewed_sample_regression(samples,labels,old_occurrences,new_occurrences):
    old_groups=Counter(key[:5] for key in old_occurrences)
    new_groups=Counter(key[:5] for key in new_occurrences)
    affected=[]
    for sample in samples:
        if sample.get("selection_basis")!="PROBABILITY_SAMPLE": continue
        sample_groups=_sample_candidate_groups(sample)
        removed=[group for group in sample_groups if old_groups[group] and not new_groups[group]]
        if removed:
            affected.append({"sample_id":sample["sample_id"],"card_name":sample["card"]["name"],"pattern_id":sample["pattern_id"],"label":labels.get(sample["sample_id"]),"removed_evidence_paths":[{"source":g[1],"source_record_identity":g[2],"token":g[3],"requirement":g[4]} for g in removed]})
    counts=Counter(r["label"] for r in affected)
    return {"samples_removed":len(affected),"CORRECT_removed":counts["CORRECT"],"WRONG_removed":counts["WRONG"],"affected_samples":affected}


def _capture_pipeline_fingerprint():
    names=("requirement_candidates.jsonl","matched_cards.jsonl","stats.json","requirement_stats.json","mapping_coverage.json","join_audit_stats.json","suspicious_join_audit.json","oracle_mismatch_audit.json","unmatched_forge.jsonl","unmatched_xmage.jsonl","ambiguous_matches.jsonl")
    result={name:sha256_file(OUT/name) for name in names}
    inventory=json.loads((OUT/"inventory.json").read_text(encoding="utf-8"))
    inventory.pop("generated_at_utc",None)
    result["inventory.semantic_sha256"]=hashlib.sha256(json.dumps(inventory,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return result


def run(reviewer_a_path):
    actual_mapping_sha=sha256_file(ROOT/"mappings.yaml")
    if actual_mapping_sha!=MAPPING_SHA: raise ValueError(f"mappings.yaml changed: {actual_mapping_sha}")
    if miner.EXTRACTOR_VERSION!="0.2.1": raise ValueError(f"Expected extractor 0.2.1, got {miner.EXTRACTOR_VERSION}")
    if dict(miner.PINNED_REVISIONS)!=SOURCE_SET: raise ValueError("Pinned source set changed")
    census=yaml.safe_load((ROOT/"guard_design.yaml").read_text(encoding="utf-8"))
    if census.get("validation_scope",{}).get("mapping_sha256")!=MAPPING_SHA or census.get("validation_scope",{}).get("source_set")!=SOURCE_SET or census.get("validation_scope",{}).get("extractor_version")!="0.2.0":
        raise ValueError("Phase 0.2C census scope is not the required parent scope")

    # Preserve the 0.2.0 evidence set once before the new pipeline overwrites its local cache output.
    baseline=OUT/"requirement_candidates.jsonl"
    if not BASELINE_CANDIDATES.exists():
        first=next(jsonl(baseline),None)
        if first is None or first.get("provenance",{}).get("extractor_version")!="0.2.0":
            raise ValueError("Current requirement_candidates.jsonl is not a complete 0.2.0 baseline")
        for row in jsonl(baseline):
            if row.get("provenance",{}).get("extractor_version")!="0.2.0" or row.get("provenance",{}).get("mapping_sha256")!=MAPPING_SHA or row.get("provenance",{}).get("source_set",{}).get("scryfall")!=SOURCE_SET["scryfall"] or row.get("provenance",{}).get("source_set",{}).get("forge")!=SOURCE_SET["forge"] or row.get("provenance",{}).get("source_set",{}).get("xmage")!=SOURCE_SET["xmage"]:
                raise ValueError("Old candidate artifact contains a different validation scope")
        shutil.copyfile(baseline,BASELINE_CANDIDATES)
    old_rows=list(jsonl(BASELINE_CANDIDATES))
    if not old_rows or any(r.get("provenance",{}).get("extractor_version")!="0.2.0" or r.get("provenance",{}).get("mapping_sha256")!=MAPPING_SHA for r in old_rows):
        raise ValueError("Saved old candidate set is not a valid 0.2.0/mapping baseline")
    old_occurrences=candidate_occurrences(old_rows,old_format=True)

    historical_paths=[ROOT/name for name in HISTORICAL_FILES]+[OUT/name for name in HISTORICAL_OUTPUTS]
    historical_hashes={str(path):sha256_file(path) for path in historical_paths if path.exists()}
    old_stats=json.loads((OUT/"stats.json").read_text(encoding="utf-8"))
    old_join_stats=json.loads((OUT/"join_audit_stats.json").read_text(encoding="utf-8"))
    review_samples=list(jsonl(OUT/"review_samples.jsonl"))
    final_labels=_review_state(reviewer_a_path)

    loaded=miner.dataset_rows(miner.load_sources())
    miner.mine.revisions=dict(SOURCE_SET)
    miner.mine.remote_revisions={}
    miner.mine(loaded)
    first_fingerprint=_capture_pipeline_fingerprint()
    miner.mine(loaded)
    second_fingerprint=_capture_pipeline_fingerprint()
    if first_fingerprint!=second_fingerprint:
        differing=sorted(k for k in set(first_fingerprint)|set(second_fingerprint) if first_fingerprint.get(k)!=second_fingerprint.get(k))
        raise ValueError(f"Two pinned 0.2.1 pipeline runs were not deterministic: {differing}")

    for path,digest in historical_hashes.items():
        if sha256_file(path)!=digest: raise ValueError(f"Historical Phase 0.2B/0.2A file changed: {path}")
    new_rows=list(jsonl(OUT/"requirement_candidates.jsonl"))
    if any(r.get("provenance",{}).get("extractor_version")!="0.2.1" or r.get("provenance",{}).get("mapping_sha256")!=MAPPING_SHA for r in new_rows):
        raise ValueError("New candidate output does not carry extractor 0.2.1 and the pinned mapping SHA")
    new_occurrences=candidate_occurrences(new_rows)
    old_keys=set(old_occurrences);new_keys=set(new_occurrences)
    removed=old_keys-new_keys;added=new_keys-old_keys
    guard_stats=miner.mine.guard_stats
    expected_removed=set()
    for source in ("forge_same_zone","xmage_import_only"):
        for row in guard_stats[source]["candidate_occurrences"]:
            expected_removed.add((str(row["oracle_id"]),"forge" if source=="forge_same_zone" else "xmage",row["source_record_identity"],row["token"],row["requirement"],int(row["occurrence_index"])))
    unexpected_removed=removed-expected_removed
    unexpected_added=added
    if added: raise ValueError(f"Guards unexpectedly added {len(added)} mapped occurrences")
    if unexpected_removed: raise ValueError(f"Found {len(unexpected_removed)} removals outside the two guards")
    if removed!=expected_removed: raise ValueError(f"Guard removals and candidate diff disagree: removed={len(removed)}, expected={len(expected_removed)}")

    same_zone_source=OUT/"forge_same_zone_occurrences.jsonl"
    forge_census=list(jsonl(same_zone_source))
    same_zone_multiset=Counter((r["source_record_identity"],r["action_type"],r["raw_action_snippet"]) for r in forge_census)
    production_same_zone_multiset=Counter((r["source_record_identity"],r["token"],r["raw_action_snippet"]) for r in guard_stats["forge_same_zone"]["all_occurrences"])
    if same_zone_multiset!=production_same_zone_multiset:
        raise ValueError("0.2.1 Forge parser did not suppress exactly the Phase 0.2C SAME_ZONE action occurrences")
    forge_previously_mapped=sum(bool(r.get("oracle_id")) and r.get("currently_mapped_requirement")=="zone_transition" for r in forge_census)
    forge_candidate_suppressed=guard_stats["forge_same_zone"]["candidate_suppressed"]
    forge_guard_candidate_keys={key for key in expected_removed if key[1]=="forge"}
    forge_still_emitted=len(forge_guard_candidate_keys & new_keys)
    if guard_stats["forge_same_zone"]["seen"]!=len(forge_census) or forge_candidate_suppressed!=forge_previously_mapped or forge_still_emitted:
        raise ValueError(f"Forge guard census mismatch: seen={guard_stats['forge_same_zone']['seen']}, census={len(forge_census)}, mapped={forge_previously_mapped}, suppressed={forge_candidate_suppressed}, still={forge_still_emitted}")

    xmage_census=list(jsonl(OUT/"xmage_usage_census.jsonl"))
    xmage_non_executable=[r for r in xmage_census if r.get("extracted_by_v0_2_0") and not r.get("executable_mentions") and (r.get("classification")=="IMPORTED_ONLY" or r.get("comment_mentions",0)+r.get("string_literal_mentions",0)+r.get("package_mentions",0)>0)]
    xmage_multiset=Counter((r["source_record_identity"],r["mapped_class"]) for r in xmage_non_executable)
    production_xmage_multiset=Counter((r["source_record_identity"],r["token"]) for r in guard_stats["xmage_import_only"]["all_occurrences"])
    if xmage_multiset!=production_xmage_multiset:
        raise ValueError("0.2.1 XMage classifier did not reproduce Phase 0.2C non-executable-only source/class cases")
    xmage_previously_mapped=sum(bool(r.get("oracle_id")) for r in xmage_non_executable)
    xmage_imported_only_seen=sum(r.get("classification")=="IMPORTED_ONLY" for r in xmage_non_executable)
    xmage_candidate_suppressed=guard_stats["xmage_import_only"]["candidate_suppressed"]
    xmage_guard_candidate_keys={key for key in expected_removed if key[1]=="xmage"}
    xmage_still_emitted=len(xmage_guard_candidate_keys & new_keys)
    if xmage_candidate_suppressed!=xmage_previously_mapped or xmage_still_emitted:
        raise ValueError(f"XMage guard census mismatch: mapped={xmage_previously_mapped}, suppressed={xmage_candidate_suppressed}, still={xmage_still_emitted}")

    unchanged_old=old_keys-removed
    unchanged_new=new_keys
    unchanged_set_match=unchanged_old==unchanged_new
    if not unchanged_set_match: raise ValueError("Unchanged mapped candidate identity sets differ after guard implementation")
    regression=reviewed_sample_regression(review_samples,final_labels,old_occurrences,new_occurrences)
    if regression["CORRECT_removed"]:
        raise ValueError(f"Guard implementation removed {regression['CORRECT_removed']} reviewed CORRECT samples: {regression['affected_samples']}")
    sample_by_id={s["sample_id"]:s for s in review_samples}
    wrong_samples=[sid for sid,label in final_labels.items() if label=="WRONG"]
    fixed_wrong=[];still_wrong=[]
    for sid in wrong_samples:
        sample=sample_by_id[sid]
        groups=_sample_candidate_groups(sample)
        if any(old_occurrences and any(k[:5]==g for k in old_occurrences) for g in groups) and any(not any(k[:5]==g for k in new_occurrences) for g in groups):
            fixed_wrong.append(sid)
        else:
            still_wrong.append(sid)
    if set(wrong_samples)!=set(KNOWN_FORGE_SAMPLE_IDS|{KNOWN_XMAGE_SAMPLE_ID}) or len(fixed_wrong)!=5 or still_wrong:
        raise ValueError(f"Known WRONG sample regression failed: fixed={fixed_wrong}, still={still_wrong}")

    join_stability={
        "same_scryfall_rows":old_stats["scryfall"]==miner.mine.last_stats["scryfall"],
        "same_forge_matches":old_stats["forge_cards"]==miner.mine.last_stats["forge_cards"],
        "same_xmage_matches":old_stats["xmage_cards"]==miner.mine.last_stats["xmage_cards"],
        "same_both_matches":old_stats["both_cards"]==miner.mine.last_stats["both_cards"],
        "same_ambiguous_count":old_stats["ambiguous"]==miner.mine.last_stats["ambiguous"],
        "same_suspicious_join_count":old_stats["suspicious_joins"]==miner.mine.last_stats["suspicious_joins"],
        "same_join_audit_actions":old_join_stats["actions"]==json.loads((OUT/"join_audit_stats.json").read_text(encoding="utf-8"))["actions"],
    }
    if not all(join_stability.values()): raise ValueError(f"Source join/matching counts changed: {join_stability}")

    removed_rows=[old_occurrences[k] for k in sorted(removed)]
    by_source=Counter(r["source"] for r in removed_rows)
    by_construct=Counter(r["external_construct"] for r in removed_rows)
    by_requirement=Counter(r["requirement"] for r in removed_rows)
    removed_oracles={r["oracle_id"] for r in removed_rows}
    removed_cards={r["oracle_id"] or r["card_name"] for r in removed_rows}
    diff={
        "old_extractor_version":"0.2.0","new_extractor_version":"0.2.1","source_set":SOURCE_SET,"mapping_sha256":MAPPING_SHA,
        "old_candidate_occurrence_count":len(old_keys),"new_candidate_occurrence_count":len(new_keys),
        "removed_occurrences":removed_rows,"added_occurrences":[new_occurrences[k] for k in sorted(added)],
        "removed_occurrence_count":len(removed),"added_occurrence_count":len(added),
        "removed_distinct_cards":len(removed_cards),"added_distinct_cards":len({new_occurrences[k]["oracle_id"] or new_occurrences[k]["card_name"] for k in added}),
        "removed_distinct_oracle_ids":len(removed_oracles),"added_distinct_oracle_ids":len({new_occurrences[k]["oracle_id"] for k in added if new_occurrences[k]["oracle_id"]}),
        "removed_by_source":dict(sorted(by_source.items())),"removed_by_external_construct":dict(sorted(by_construct.items())),"removed_by_requirement":dict(sorted(by_requirement.items())),
        "unexpected_removed_occurrences":[old_occurrences[k] for k in sorted(unexpected_removed)],"unexpected_added_occurrences":[new_occurrences[k] for k in sorted(unexpected_added)],
        "unchanged_candidate_identity_count":len(unchanged_old),"unchanged_candidate_identity_sha256":_digest(unchanged_old),
        "unchanged_candidate_identity_set_match":unchanged_set_match,
        "guard_census":{
            "forge_same_zone_occurrences_seen":guard_stats["forge_same_zone"]["seen"],"forge_previously_mapped":forge_previously_mapped,"forge_now_suppressed":forge_candidate_suppressed,"forge_still_emitted":forge_still_emitted,
            "xmage_imported_only_occurrences_seen":xmage_imported_only_seen,"xmage_non_executable_only_occurrences_seen":len(xmage_non_executable),"xmage_previously_mapped":xmage_previously_mapped,"xmage_now_suppressed":xmage_candidate_suppressed,"xmage_still_emitted":xmage_still_emitted,
        },
        "review_regression":regression,"known_wrong":{"total":5,"fixed":len(fixed_wrong),"still_emitted":len(still_wrong),"fixed_sample_ids":sorted(fixed_wrong),"still_emitted_sample_ids":sorted(still_wrong)},
        "source_join_stability":join_stability,"pipeline_determinism":{"first_run":first_fingerprint,"second_run":second_fingerprint,"identical":True},
    }
    write_json(ROOT/"extractor_0_2_0_to_0_2_1_diff.json",diff)
    manifest={
        "extractor_version":"0.2.1","parent_extractor_version":"0.2.0","source_set":SOURCE_SET,"mapping_sha256":MAPPING_SHA,
        "validation_scope":{"extractor_version":"0.2.1","mapping_sha256":MAPPING_SHA,"source_set":SOURCE_SET},
        "guards":{
            "forge_same_zone":{"enabled":True,"predicate":"For an individual ChangeZone or ChangeZoneAll action, suppress only when Origin and Destination each parse as one recognized zone and normalize to the same value. Missing, multi-valued, dynamic, and unrecognized endpoints remain eligible."},
            "xmage_import_only":{"enabled":True,"predicate":"For a mapped semantic class in one XMage record, suppress only when the lexical classifier proves there is no executable reference and every visible reference is confined to imports, package declarations, comments, or string/char literals. Unresolved cases without positive non-executable-only proof are retained."},
        },
        "differential":{"artifact":"extractor_0_2_0_to_0_2_1_diff.json","removed_occurrences":diff["removed_occurrence_count"],"added_occurrences":diff["added_occurrence_count"],"removed_distinct_cards":diff["removed_distinct_cards"],"removed_distinct_oracle_ids":diff["removed_distinct_oracle_ids"],"unchanged_candidate_identity_sha256":diff["unchanged_candidate_identity_sha256"]},
        "validation":{"phase_0_2b_scope_inherited":False,"differential_revalidation_required":True,"phase_0_2b_extractor_version":"0.2.0","reviewed_correct_removed":regression["CORRECT_removed"],"known_wrong_fixed":len(fixed_wrong),"known_wrong_still_emitted":len(still_wrong),"new_precision_calculated":False},
    }
    (ROOT/"extractor_0_2_1_manifest.yaml").write_text(yaml.safe_dump(manifest,sort_keys=False,allow_unicode=True),encoding="utf-8")
    write_report(diff,manifest)
    if sha256_file(ROOT/"mappings.yaml")!=MAPPING_SHA: raise ValueError("mappings.yaml changed during differential run")
    for path,digest in historical_hashes.items():
        if sha256_file(path)!=digest: raise ValueError(f"Historical file changed during run: {path}")
    return diff,manifest


def write_report(diff,manifest):
    forge=diff["guard_census"];review=diff["review_regression"]
    lines=[
        "# Extractor 0.2.1 — Guard Implementation", "",
        "## Scope", "",
        f"Pinned revisions: Scryfall `{SOURCE_SET['scryfall']}`, Forge `{SOURCE_SET['forge']}`, XMage `{SOURCE_SET['xmage']}`. Mapping SHA-256 `{MAPPING_SHA}`. Extractor `0.2.0` to `0.2.1`.",
        "Only the per-action Forge same-zone guard and XMage import-only guard were implemented. Source joins, mappings, and the historical Phase 0.2B review files remain unchanged.", "",
        "## Forge same-zone guard", "",
        f"The pinned Phase 0.2C audit's {forge['forge_same_zone_occurrences_seen']} same-zone actions were all detected and suppressed individually. {forge['forge_previously_mapped']} matched action occurrences previously mapped to `zone_transition`; {forge['forge_now_suppressed']} were removed and {forge['forge_still_emitted']} remain. Mixed records retain their other cross-zone actions.", "",
        "## XMage import-only guard", "",
        f"All {forge['xmage_imported_only_occurrences_seen']} imported-only mapped class records from the Phase 0.2C census were reproduced. {forge['xmage_previously_mapped']} were mapped candidate evidence before the guard; {forge['xmage_now_suppressed']} were removed and {forge['xmage_still_emitted']} remain. Instantiated, executable-reference, and unresolved usage is retained.", "",
        "## Differential candidate impact", "",
        f"Removed mapped evidence occurrences: {diff['removed_occurrence_count']}; added: {diff['added_occurrence_count']}. Removed distinct cards: {diff['removed_distinct_cards']}; Oracle IDs: {diff['removed_distinct_oracle_ids']}. By source: `{diff['removed_by_source']}`. By construct: `{diff['removed_by_external_construct']}`. By requirement: `{diff['removed_by_requirement']}`.",
        f"Unexpected removals: {len(diff['unexpected_removed_occurrences'])}; unexpected additions: {len(diff['unexpected_added_occurrences'])}. The 104-occurrence Phase 0.2C estimate was recomputed from the candidate-set diff; actual removals are {diff['removed_occurrence_count']}.", "",
        "## Reviewed-sample regression", "",
        f"Final Phase 0.2B `CORRECT` sample removals: {review['CORRECT_removed']} / 455. Candidate paths removed in total: {review['samples_removed']} (CORRECT {review['CORRECT_removed']}, WRONG {review['WRONG_removed']}). Sample IDs and labels were not changed.", "",
        "## Known-WRONG regression", "",
        f"Known WRONG samples: {diff['known_wrong']['total']}; fixed: {diff['known_wrong']['fixed']}; still emitted: {diff['known_wrong']['still_emitted']}. Fixed IDs: `{diff['known_wrong']['fixed_sample_ids']}`.", "",
        "## Identity stability", "",
        f"Old unchanged identity set equals the new candidate identity set: **{diff['unchanged_candidate_identity_set_match']}**. Unchanged set size: {diff['unchanged_candidate_identity_count']}; SHA-256 `{diff['unchanged_candidate_identity_sha256']}`. Two complete pinned pipeline runs produced identical candidate, join, statistics, and semantic inventory outputs.",
        "", "## Historical validation scope", "",
        "Phase 0.2B results remain bound to extractor 0.2.0. Extractor 0.2.1 has NOT inherited Phase 0.2B confidence intervals automatically. No new precision or eligibility result was calculated.",
        "", "## Differential validation requirements", "",
        "Phase 0.2C.2 must review the differential under the 0.2.1 scope before any pattern precision is claimed. The 0.2B intervals cannot be carried forward. No new review samples were created in this phase.", "",
    ]
    (ROOT/"EXTRACTOR_0_2_1_REPORT.md").write_text("\n".join(lines),encoding="utf-8")


def main():
    p=argparse.ArgumentParser(description="Run pinned 0.2.1 guard differential")
    p.add_argument("--reviewer-a",required=True,help="Final Reviewer-A 460-row YAML used for regression labels")
    args=p.parse_args()
    diff,_=run(args.reviewer_a)
    print(json.dumps({"status":"COMPLETE","removed":diff["removed_occurrence_count"],"added":diff["added_occurrence_count"],"correct_removed":diff["review_regression"]["CORRECT_removed"],"known_wrong_fixed":diff["known_wrong"]["fixed"]},sort_keys=True))


if __name__=="__main__": main()
