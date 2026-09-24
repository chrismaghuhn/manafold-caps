"""Phase 0.2B review aggregation with strict sample/input validation."""
from __future__ import annotations

import argparse
import hashlib
import math
from collections import Counter
from pathlib import Path

import yaml

from src.cap_miner import interval_method_for_population, hypergeometric_interval, wilson_interval
from src.cap_miner import PINNED_REVISIONS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"output"
EXPECTED_BATCH="phase-0.2a-batch-1"
EXPECTED_A=460
EXPECTED_B=208
EXPECTED_FINAL={"CORRECT":455,"WRONG":5}
EXPECTED_ADJUDICATIONS={
    "053d9fe47d105986611506c8":"WRONG",
    "80e88eda5a088379b9af218a":"WRONG",
    "23a6562a6e6a5c5879b55310":"WRONG",
    "532892f8dc083b10a99ec57d":"WRONG",
}
VALID_DECISIONS={"CORRECT","TOO_BROAD","TOO_NARROW","CONTEXT_DEPENDENT","WRONG","AMBIGUOUS","SOURCE_EVIDENCE_INSUFFICIENT"}
DECISIVE={"CORRECT","TOO_BROAD","TOO_NARROW","CONTEXT_DEPENDENT","WRONG"}


def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_yaml(path):
    value=yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise ValueError(f"Expected YAML mapping in {path}")
    return value


def read_json(path):
    import json
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_result_files(paths, expected_reviewer, batch=EXPECTED_BATCH):
    rows=[]; metadata=[]; issues=[]
    for path in paths:
        data=read_yaml(path)
        if data.get("reviewer_id")!=expected_reviewer:
            issues.append(f"{Path(path).name}: reviewer_id is {data.get('reviewer_id')!r}, expected {expected_reviewer!r}")
        if data.get("review_batch_id")!=batch:
            issues.append(f"{Path(path).name}: review_batch_id is {data.get('review_batch_id')!r}, expected {batch!r}")
        if not isinstance(data.get("decisions"),list):
            issues.append(f"{Path(path).name}: decisions is missing or not a list")
            continue
        metadata.append({"file":Path(path).name,"sha256":sha256(path),"rows":len(data["decisions"]),"review_scope":data.get("review_scope")})
        for entry in data["decisions"]:
            sid=entry.get("sample_id"); decision=entry.get("decision")
            if not sid: issues.append(f"{Path(path).name}: row without sample_id");continue
            if decision not in VALID_DECISIONS: issues.append(f"{Path(path).name}: {sid} has invalid decision {decision!r}");continue
            rows.append({**entry,"reviewer_id":expected_reviewer,"_input_file":Path(path).name})
    by_id={}; conflicting=[];duplicate_n=0
    for row in rows:
        sid=row["sample_id"]
        if sid in by_id:
            duplicate_n+=1
            if by_id[sid]["decision"]!=row["decision"]:
                conflicting.append(sid)
            # Copies are deduplicated only when the label agrees.
        else: by_id[sid]=row
    if conflicting: issues.append(f"{expected_reviewer}: conflicting duplicate sample labels for {len(conflicting)} IDs")
    return {"rows":rows,"by_id":by_id,"metadata":metadata,"issues":issues,"duplicate_rows":duplicate_n,"conflicting_duplicate_ids":conflicting}


def validate_review_subset(reviewer_a_ids, reviewer_b_ids, expected_n=EXPECTED_B):
    a=set(reviewer_a_ids);b=set(reviewer_b_ids);intersection=a&b
    return {"required_n":expected_n,"reviewer_b_n":len(b),"verified_n":len(intersection),"subset_valid":b<=a and len(b)==expected_n,"missing_from_a":sorted(b-a)}


def split_packet_samples(packet):
    primary=[row for row in packet if row.get("selection_basis")=="PROBABILITY_SAMPLE"]
    forced=[row for row in packet if row.get("selection_basis")=="FORCED_FLAGGED_JOIN_AUDIT"]
    unknown=[row for row in packet if row.get("selection_basis") not in {"PROBABILITY_SAMPLE","FORCED_FLAGGED_JOIN_AUDIT"}]
    if unknown: raise ValueError(f"Unknown review selection_basis on {len(unknown)} packet rows")
    return primary,forced


def nominal_agreement(labels_a,labels_b):
    if len(labels_a)!=len(labels_b) or not labels_a:
        return {"n":min(len(labels_a),len(labels_b)),"raw_agreement":None,"cohen_kappa":None,"gwet_ac1":None,"status":"NOT_AVAILABLE"}
    n=len(labels_a);raw=sum(a==b for a,b in zip(labels_a,labels_b))/n
    categories=sorted(set(labels_a)|set(labels_b))
    p_a=Counter(labels_a);p_b=Counter(labels_b)
    expected=sum((p_a[c]/n)*(p_b[c]/n) for c in categories)
    kappa=None if math.isclose(1-expected,0) else (raw-expected)/(1-expected)
    pooled=Counter(labels_a+labels_b);q=len(categories);total=2*n
    chance=0.0 if q<=1 else sum((pooled[c]/total)*(1-pooled[c]/total) for c in categories)/(q-1)
    ac1=None if math.isclose(1-chance,0) else (raw-chance)/(1-chance)
    a_single_category=len(set(labels_a))==1
    return {"n":n,"raw_agreement":raw,"cohen_kappa":kappa,"gwet_ac1":ac1,"categories":categories,"cohen_kappa_denominator_zero":math.isclose(1-expected,0),"single_category_reviewer_a_marginal_warning":a_single_category,"status":"CALCULATED"}


def build_adjudications(disagreement_data, samples_by_id):
    entries=disagreement_data.get("disagreements",[])
    result=[];issues=[]
    if len(entries)!=4: issues.append(f"Expected exactly 4 disagreements, received {len(entries)}")
    seen=set()
    for d in entries:
        sid=d.get("sample_id")
        if sid in seen: issues.append(f"Duplicate disagreement record {sid}")
        seen.add(sid)
        expected=EXPECTED_ADJUDICATIONS.get(sid)
        recommended=d.get("recommended_resolution")
        if expected is None or recommended!=expected: issues.append(f"Unexpected recommended adjudication for {sid}: {recommended!r}")
        if d.get("reviewer_a")!="CORRECT" or d.get("reviewer_b")!="WRONG": issues.append(f"Unexpected reviewer labels in disagreement artifact for {sid}")
        sample=samples_by_id.get(sid)
        if sample is None: issues.append(f"Disagreement sample {sid} is absent from the primary review packet");continue
        forge=sample.get("evidence",{}).get("forge",{})
        params=forge.get("parameters",{})
        origins=params.get("Origin",[]);destinations=params.get("Destination",[])
        if "Library" not in origins or "Library" not in destinations:
            issues.append(f"Adjudication evidence for {sid} does not show Library-to-Library")
        result.append({"sample_id":sid,"card_name":d.get("card_name"),"pattern_id":d.get("pattern_id"),"reviewer_a_label":d.get("reviewer_a"),"reviewer_b_label":d.get("reviewer_b"),"final_label":expected or recommended,"rationale":"The sampled Forge occurrence has Origin=Library and Destination=Library. It performs within-library selection or repositioning rather than crossing a zone boundary, so this occurrence does not support zone_transition.","evidence":{"forge_constructs":forge.get("selected_constructs",[]),"origin":origins,"destination":destinations,"source_record_identity":forge.get("source_record_identity")},"decision_source":"review_disagreements_a_vs_b.yaml; recommendation accepted per task"})
    if seen!=set(EXPECTED_ADJUDICATIONS): issues.append("Disagreement sample IDs do not match the four required adjudications")
    return result,issues


def pattern_aggs(final_by_id, primary_samples, pattern_inventory):
    output=[]
    for p in pattern_inventory["patterns"]:
        sample_ids=p.get("probability_sample_ids",p.get("sample_ids",[]))
        counts=Counter(final_by_id[sid] for sid in sample_ids if sid in final_by_id)
        decisive_n=sum(counts[label] for label in DECISIVE)
        population=p["population_size"];n=p["probability_sample_size"]
        method=interval_method_for_population(population,n)
        if decisive_n:
            if method=="FINITE_POPULATION_HYPERGEOMETRIC": interval=hypergeometric_interval(population,decisive_n,counts["CORRECT"])
            else: interval=wilson_interval(counts["CORRECT"],decisive_n)
        else:
            interval={"estimate":None,"reviewed_n":0,"accepted_n":0,"confidence_level":0.95,"interval_method":"wilson" if method=="WILSON_BINOMIAL" else "hypergeometric","lower":None,"upper":None}
        output.append({"pattern_id":p["pattern_id"],"population_size":population,"probability_sample_size":n,"counts":{label:counts[label] for label in sorted(VALID_DECISIONS)},"decisive_n":decisive_n,"precision_estimate":counts["CORRECT"]/decisive_n if decisive_n else None,"confidence_level":0.95,"interval_method":method,"lower":interval.get("lower"),"upper":interval.get("upper"),"validation_status":"REVIEW_COMPLETE"})
    return output


def finalize_primary_decisions(reviewer_a, reviewer_b, adjudications):
    a={sid:(row["decision"] if isinstance(row,dict) else row) for sid,row in reviewer_a.items()}
    b={sid:(row["decision"] if isinstance(row,dict) else row) for sid,row in reviewer_b.items()}
    if len(a)!=EXPECTED_A or len(b)!=EXPECTED_B: raise ValueError("Incomplete reviewer result set")
    if not set(b)<=set(a): raise ValueError("Reviewer B IDs must be a subset of Reviewer A")
    disagreements={sid for sid in b if a[sid]!=b[sid]}
    adjudication_map={row["sample_id"]:row["final_label"] for row in adjudications}
    if set(adjudication_map)!=disagreements: raise ValueError("Adjudication results must cover exactly all reviewer disagreements")
    final=dict(a)
    final.update(adjudication_map)
    counts=Counter(final.values())
    observed={"CORRECT":counts["CORRECT"],"WRONG":counts["WRONG"]}
    if observed!=EXPECTED_FINAL: raise ValueError(f"Final primary results do not match task expectation: {observed}")
    return final,counts


def aggregate_review_inputs(reviewer_a_paths, reviewer_b_path, disagreements_path, forced_path, output_dir=OUT):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    inventory=read_json(OUT/"pattern_inventory.json")
    if inventory.get("validation_scope",{}).get("source_set")!={**PINNED_REVISIONS}:
        raise ValueError("Pattern inventory dataset revisions are not the Phase 0.2B pinned source set")
    packet=[__import__("json").loads(line) for line in (OUT/"review_samples.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    primary,forced_samples=split_packet_samples(packet)
    samples_by_id={r["sample_id"]:r for r in primary}
    if len(samples_by_id)!=len(primary): raise ValueError("Duplicate primary sample IDs in review packet")
    a=load_result_files(reviewer_a_paths,"reviewer-a");b=load_result_files([reviewer_b_path],"reviewer-b")
    disagreements=read_yaml(disagreements_path)
    adjudications,adjudication_issues=build_adjudications(disagreements,samples_by_id)
    forced=load_result_files([forced_path],"reviewer-a")
    issues=[*a["issues"],*b["issues"],*adjudication_issues]
    packet_ids=set(samples_by_id);a_ids=set(a["by_id"]);b_ids=set(b["by_id"])
    if len(primary)!=EXPECTED_A: issues.append(f"Primary packet has {len(primary)} probability samples, expected {EXPECTED_A}")
    if len(a_ids)!=EXPECTED_A: issues.append(f"Reviewer A has {len(a_ids)} unique result IDs, expected {EXPECTED_A}")
    if len(b_ids)!=EXPECTED_B: issues.append(f"Reviewer B has {len(b_ids)} unique result IDs, expected {EXPECTED_B}")
    subset=validate_review_subset(a_ids,b_ids)
    if not subset["subset_valid"]: issues.append(f"Reviewer B has {len(b_ids-a_ids)} IDs absent from Reviewer A; B must be an exact {EXPECTED_B}-item subset of A")
    disagreement_ids={r["sample_id"] for r in adjudications}
    if disagreement_ids-a_ids: issues.append(f"The disagreement artifact supplies Reviewer-A labels for {len(disagreement_ids-a_ids)} IDs absent from the Reviewer-A result files")
    if not b_ids<=packet_ids: issues.append(f"Reviewer B has {len(b_ids-packet_ids)} IDs absent from primary packet")
    if not a_ids<=packet_ids: issues.append(f"Reviewer A has {len(a_ids-packet_ids)} IDs absent from primary packet")
    if len(adjudications)!=4: issues.append(f"Only {len(adjudications)} of the required four disagreements could be adjudicated")
    reviewer_comparison=disagreements.get("comparison",{})
    # The supplied disagreement file contains A labels for the four conflict rows;
    # verify those labels against the component files whenever a row is present there.
    for item in adjudications:
        sid=item["sample_id"]
        if sid in a["by_id"] and a["by_id"][sid]["decision"]!=item["reviewer_a_label"]: issues.append(f"Reviewer A disagreement label conflicts for {sid}")
        if sid in b["by_id"] and b["by_id"][sid]["decision"]!=item["reviewer_b_label"]: issues.append(f"Reviewer B disagreement label conflicts for {sid}")

    forced_ids={r["sample_id"] for r in forced_samples}
    if set(forced["by_id"])!=forced_ids: issues.append("Forced audit results do not match forced audit packet IDs")
    if len(forced_samples)!=1 or len(forced["by_id"])!=1: issues.append("Expected exactly one separate forced audit result")
    forced_summary={"items":len(forced["by_id"]),"counts":dict(Counter(v["decision"] for v in forced["by_id"].values())),"included_in_primary":False}

    a_raw=len(a["rows"]);a_unique=len(a["by_id"]);a_counts=Counter(v["decision"] for v in a["by_id"].values())
    b_counts=Counter(v["decision"] for v in b["by_id"].values())
    if a_unique==EXPECTED_A and {k:v for k,v in a_counts.items() if v}!={"CORRECT":459,"WRONG":1}:
        issues.append(f"Reviewer A label counts are {dict(a_counts)}, expected 459 CORRECT and 1 WRONG")
    if len(b_ids)==EXPECTED_B and {k:v for k,v in b_counts.items() if v}!={"CORRECT":204,"WRONG":4}:
        issues.append(f"Reviewer B label counts are {dict(b_counts)}, expected 204 CORRECT and 4 WRONG")
    duplicate_overlap=a_raw-a_unique
    compared_ids=a_ids&b_ids
    agreement={"status":"NOT_AVAILABLE","n":0,"raw_agreement":None,"cohen_kappa":None,"gwet_ac1":None,"reason":"Requires all 208 blind B IDs to be present in A results."}
    if len(compared_ids)==EXPECTED_B and b_ids<=a_ids:
        ordered=sorted(b_ids)
        agreement=nominal_agreement([a["by_id"][sid]["decision"] for sid in ordered],[b["by_id"][sid]["decision"] for sid in ordered])
    else:
        agreement["provided_comparison_unverified"]=reviewer_comparison

    adjudication_doc={"review_batch_id":EXPECTED_BATCH,"decision_count":len(adjudications),"unresolved":len(adjudication_issues),"decisions":adjudications}
    (ROOT/"adjudication_results.yaml").write_text(yaml.safe_dump(adjudication_doc,sort_keys=False,allow_unicode=True),encoding="utf-8")

    status="BLOCKED_INPUT_INCOMPLETE" if issues else "REVIEW_COMPLETE"
    final_counts=None;pattern_results=[]
    if not issues:
        final_by_id,final_counts=finalize_primary_decisions(a["by_id"],b["by_id"],adjudications)
        pattern_results=pattern_aggs(final_by_id,primary,inventory)

    reviewer_counts={"reviewer_a":{"files":a["metadata"],"raw_decision_rows":a_raw,"unique_sample_ids":a_unique,"duplicate_rows_deduplicated":duplicate_overlap,"labels":dict(a_counts),"expected_unique":EXPECTED_A,"missing_primary_ids":len(packet_ids-a_ids),"disagreement_a_labels_missing_from_result_files":len(disagreement_ids-a_ids),"other_missing_reviewer_a_ids":len(packet_ids-a_ids)-len(disagreement_ids-a_ids)},"reviewer_b":{"files":b["metadata"],"unique_sample_ids":len(b_ids),"labels":dict(b_counts),"expected_unique":EXPECTED_B,"ids_in_a":len(b_ids&a_ids),"ids_missing_in_a":len(b_ids-a_ids)},"double_review_subset":subset}
    validation={"status":status,"review_batch_id":EXPECTED_BATCH,"validation_scope":inventory["validation_scope"],"input_provenance":{"reviewer_a_files":a["metadata"],"reviewer_b_file":b["metadata"],"disagreement_file":{"file":Path(disagreements_path).name,"sha256":sha256(disagreements_path)},"forced_audit_file":{"file":Path(forced_path).name,"sha256":sha256(forced_path)}},"reviewer_counts":reviewer_counts,"agreement":agreement,"adjudication":{"count":len(adjudications),"unresolved":len(adjudication_issues),"file":"adjudication_results.yaml"},"forced_audit_summary":forced_summary,"expected_primary_final_counts":{"total":460,"CORRECT":455,"WRONG":5},"primary_final_counts":dict(final_counts) if final_counts is not None else None,"pattern_results":pattern_results,"blocking_issues":issues}
    (ROOT/"validation_results.yaml").write_text(yaml.safe_dump(validation,sort_keys=False,allow_unicode=True),encoding="utf-8")
    write_aggregation_report(validation,adjudications,reviewer_comparison)
    return validation


def write_aggregation_report(validation,adjudications,provided_comparison):
    counts=validation["reviewer_counts"];issues=validation["blocking_issues"];agreement=validation["agreement"]
    a_counts=counts["reviewer_a"]["labels"]
    a_unique=counts["reviewer_a"]["unique_sample_ids"]
    lines=["# Phase 0.2B — Review Aggregation, Adjudication & Pattern Precision","",f"Status: **{validation['status']}**. Pinned validation scope: `{validation['validation_scope']}`.","", "## Review coverage", "",f"Reviewer A inputs contain {counts['reviewer_a']['raw_decision_rows']} raw rows and {counts['reviewer_a']['unique_sample_ids']} unique IDs (expected {EXPECTED_A}); duplicate rows deduplicated: {counts['reviewer_a']['duplicate_rows_deduplicated']}. Available unique Reviewer-A labels: `{a_counts}`.",f"Reviewer B supplied {counts['reviewer_b']['unique_sample_ids']} IDs (expected {EXPECTED_B}); {counts['double_review_subset']['verified_n']} match the A files and {counts['reviewer_b']['ids_missing_in_a']} are absent. Exact-subset validation: **{counts['double_review_subset']['subset_valid']}**.",f"Forced audit: {validation['forced_audit_summary']['items']} separate item(s), labels `{validation['forced_audit_summary']['counts']}`; excluded from primary counts and all precision calculations.","", "## Agreement", ""]
    lines += [f"Available Reviewer-A labels: `{a_counts}`; expected when complete: 459 CORRECT and 1 WRONG.",f"The supplied A-150 file duplicates the 150-item pilot contained in the cumulative A-300 file. Of {EXPECTED_A-a_unique} missing A IDs, {counts['reviewer_a']['disagreement_a_labels_missing_from_result_files']} have an A label only in the disagreement artifact; {counts['reviewer_a']['other_missing_reviewer_a_ids']} have no A label in any supplied result file."]
    if agreement["status"]=="CALCULATED":
        lines += [f"Pre-adjudication agreement on all {agreement['n']} blind items: raw {agreement['raw_agreement']:.6f}; Cohen's κ {agreement['cohen_kappa']}; Gwet's AC1 {agreement['gwet_ac1']:.6f}."]
        if agreement.get("single_category_reviewer_a_marginal_warning"):
            lines += ["Reviewer A used one label category on this double-reviewed subset. Cohen's κ is degenerate under these marginals and is not interpreted as poor agreement; raw agreement and AC1 are reported alongside it."]
    else:
        lines += ["Agreement metrics were not calculated because the supplied Reviewer-A files are incomplete and Reviewer B's IDs are not an exact subset of A. The disagreement YAML contains a precomputed comparison, but it cannot be independently verified and is not reported as an aggregation result.",f"Provided comparison artifact (unverified): {provided_comparison}."]
    lines += ["", "## Adjudication", "",f"Accepted the four supplied recommendations as `WRONG`; {len(adjudications)} decisions are written to `adjudication_results.yaml`. The four A labels appear in the disagreement artifact but are absent from the Reviewer-A result files.",""]
    lines += [f"- `{a['sample_id']}` — `{a['card_name']}` / `{a['pattern_id']}`: Reviewer A `{a['reviewer_a_label']}`, Reviewer B `{a['reviewer_b_label']}`, final `{a['final_label']}`. {a['rationale']}" for a in adjudications]
    lines += ["", "## Final primary results", ""]
    if validation["primary_final_counts"] is None:
        lines += [f"Not computed. Expected, if the complete review set validates: 460 total (455 CORRECT, 5 WRONG). Current A input has {counts['reviewer_a']['unique_sample_ids']} unique IDs, so no pattern precision or interval is emitted."]
    else:
        primary=validation["primary_final_counts"]
        lines += [f"Final labels: `{primary}` (total {sum(primary.values())}). Forced audit labels remain separate."]
    lines += ["", "## Pattern table", ""]
    if validation["pattern_results"]:
        lines += ["| pattern | population | probability n | CORRECT | TOO_BROAD | TOO_NARROW | CONTEXT_DEPENDENT | WRONG | AMBIGUOUS | SOURCE_EVIDENCE_INSUFFICIENT | decisive n | precision | interval | lower | upper |","|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
        for p in validation["pattern_results"]:
            lines.append(f"| `{p['pattern_id']}` | {p['population_size']} | {p['probability_sample_size']} | {p['counts']['CORRECT']} | {p['counts']['TOO_BROAD']} | {p['counts']['TOO_NARROW']} | {p['counts']['CONTEXT_DEPENDENT']} | {p['counts']['WRONG']} | {p['counts']['AMBIGUOUS']} | {p['counts']['SOURCE_EVIDENCE_INSUFFICIENT']} | {p['decisive_n']} | {p['precision_estimate']} | `{p['interval_method']}` | {p['lower']} | {p['upper']} |")
    else: lines += ["Unavailable until the missing Reviewer-A reviews are supplied and all 208 B IDs are verified as an exact subset."]
    lines += ["", "## Validation findings", "", "The four supplied adjudications identify Forge `ChangeZone` / `ChangeZoneAll` occurrences with `Origin=Library` and `Destination=Library`; those occurrences reposition cards within the library and do not support a zone-boundary transition. The existing XMage unused-import lexical false positive is Reviewer A's `xmage.destroy_target_effect.v1` WRONG result in the supplied unique-ID subset. These findings do not change mappings or extractor behavior.","", "## Requirement-level status", "", "No Requirement-level precision is calculated or combined. `requirement_evidence_projection.yaml` remains unchanged; source-specific pattern paths and cross corroboration are separate.","", "## Next-step blockers/findings", ""]
    lines += [f"- {issue}" for issue in issues]
    lines += ["",f"Supply the missing {counts['reviewer_a']['missing_primary_ids']} Reviewer-A primary decisions, including A labels for all 208 B double-review IDs (the current A files are missing 160 of those IDs; four A labels appear only in the disagreement artifact). Then rerun aggregation; the original reviewer files will remain untouched.",""]
    (ROOT/"REVIEW_AGGREGATION_REPORT.md").write_text("\n".join(lines),encoding="utf-8")


def run_cli():
    parser=argparse.ArgumentParser(description="Aggregate Phase 0.2B human review result YAMLs")
    parser.add_argument("--reviewer-a",action="append",required=True,help="Reviewer-A result YAML; repeat for split files")
    parser.add_argument("--reviewer-b",required=True)
    parser.add_argument("--disagreements",required=True)
    parser.add_argument("--forced-audit",required=True)
    args=parser.parse_args()
    validation=aggregate_review_inputs(args.reviewer_a,args.reviewer_b,args.disagreements,args.forced_audit)
    print(f"Aggregation status: {validation['status']}")
    if validation["blocking_issues"]:
        for issue in validation["blocking_issues"]: print(f"BLOCKED: {issue}")
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(run_cli())
