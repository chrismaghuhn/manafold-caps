"""Generate the exhaustive blind review packet for 0.2.0 -> 0.2.1 removals."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from src import cap_miner as miner
from src.guard_differential import candidate_occurrences, jsonl, sha256_file

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"output"
SOURCE_SET=dict(miner.PINNED_REVISIONS)
DIFF_PATH=ROOT/"extractor_0_2_0_to_0_2_1_diff.json"
MANIFEST_PATH=ROOT/"extractor_0_2_1_manifest.yaml"
UNCHANGED_DIGEST="07335ad502e4512712de0af6e4d8cd7fb0322d0a49952fc9826c8cc66b20c36f"
EXPECTED_REMOVED=104
EXPECTED_BY_GUARD={"FORGE_SAME_ZONE":98,"XMAGE_IMPORT_ONLY":6}
REVIEW_BATCH="phase-0.2c-2-differential-v1"
REVIEW_DECISIONS={"REMOVAL_CORRECT","REMOVAL_WRONG","AMBIGUOUS","SOURCE_EVIDENCE_INSUFFICIENT"}


def validate_review_decision(decision):
    if decision not in REVIEW_DECISIONS:
        raise ValueError(f"Unknown differential removal-review decision: {decision}")
    return decision


def _identity_key(row):
    return (str(row["oracle_id"]),row["source"],row["source_record_identity"],row["external_construct"],row["requirement"],int(row["occurrence_index"]))


def _sample_id(guard_type,identity):
    guard_version="forge.same_zone.v1" if guard_type=="FORGE_SAME_ZONE" else "xmage.non_executable_only.v1"
    payload=json.dumps([guard_version,identity],ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return "differential:"+hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _record_index(source_record_identity):
    match=re.search(r":row:(\d+)$",source_record_identity)
    if not match: raise ValueError(f"Invalid stable source record identity: {source_record_identity}")
    return int(match.group(1))


def forge_action_occurrences(record):
    text=record.get("output") or miner.all_strings(record)
    text=str(text).replace("\\n","\n")
    counts=Counter();result=[]
    pattern=r"(?:^|[\n\r|:])\s*(?:(?:A:)?(?:AB|SP|DB)\$|[TS]:Mode\$)\s*([^|\r\n]+)([^\r\n]*)"
    for match in re.finditer(pattern,text):
        action=match.group(1).strip()
        if not action or not re.fullmatch(r"[\w.-]+",action): continue
        occurrence_index=counts[action];counts[action]+=1
        line=match.group(0).strip();fields=defaultdict(list)
        for key,value in re.findall(r"\b([A-Za-z][\w]*)\$\s*([^|\r\n]+)",line):
            fields[key].append(value.strip().strip('"').strip())
        result.append({"action_type":action,"occurrence_index":occurrence_index,"parameters":dict(fields),"raw_action_snippet":line})
    return result


def java_reference_contexts(source,class_name):
    code,comments,literals=miner.strip_java_non_code(source,include_contexts=True)
    executable=re.sub(r"(?m)^\s*(?:import\s+(?:static\s+)?[^;]+;|package\s+[^;]+;)","",code)
    masks=[
        ("IMPORT",source,r"(?m)^\s*import\s+(?:static\s+)?[^;]*"+re.escape(class_name)+r"[^;]*;"),
        ("PACKAGE",source,r"(?m)^\s*package\s+[^;]*"+re.escape(class_name)+r"[^;]*;"),
        ("COMMENT",comments,r"\b"+re.escape(class_name)+r"\b"),
        ("STRING_OR_CHAR_LITERAL",literals,r"\b"+re.escape(class_name)+r"\b"),
        ("EXECUTABLE",executable,r"\b"+re.escape(class_name)+r"\b"),
    ]
    result=[]
    for kind,text,pattern in masks:
        for match in re.finditer(pattern,text):
            line_number=text.count("\n",0,match.start())+1
            lines=source.splitlines()
            line=lines[line_number-1] if line_number<=len(lines) else ""
            result.append({"context":kind,"line":line_number,"source_line":line.strip()})
    order={"IMPORT":0,"PACKAGE":1,"COMMENT":2,"STRING_OR_CHAR_LITERAL":3,"EXECUTABLE":4}
    return sorted(result,key=lambda r:(r["line"],order[r["context"]],r["source_line"]))


def _canonical_card(card):
    faces=card.get("card_faces") or []
    return {
        "oracle_id":card.get("oracle_id"),"name":card.get("name"),"type_line":card.get("type_line"),
        "layout":card.get("layout"),"mana_cost":card.get("mana_cost"),"oracle_text":card.get("oracle_text"),
        "canonical_oracle":{"parent_text":card.get("oracle_text"),"faces":[{"name":f.get("name"),"oracle_text":f.get("oracle_text")} for f in faces if isinstance(f,dict)]},
    }


def build_forge_review_item(removed,card,record,occurrences):
    identity=_identity_key(removed)
    selected=[row for row in occurrences if row["action_type"]==removed["external_construct"] and row["occurrence_index"]==removed["occurrence_index"]]
    if len(selected)!=1: raise ValueError(f"Forge removed occurrence lacks unique action-local source evidence: {identity}")
    chosen=selected[0]
    if chosen["parameters"].get("Origin",[])!=["Library"] or chosen["parameters"].get("Destination",[])!=["Library"]:
        raise ValueError(f"Forge differential occurrence is no longer the audited Library-to-Library shape: {identity}")
    card_payload=_canonical_card(card)
    old_identity={"oracle_id":removed["oracle_id"],"source":removed["source"],"source_record_identity":removed["source_record_identity"],"external_construct":removed["external_construct"],"requirement":removed["requirement"],"occurrence_index":removed["occurrence_index"]}
    sample={
        "differential_sample_id":_sample_id("FORGE_SAME_ZONE",old_identity),"old_occurrence_identity":old_identity,
        "guard_version":"forge.same_zone.v1",
        "oracle_id":removed["oracle_id"],"card_name":removed["card_name"],"source":"forge",
        "source_record_identity":removed["source_record_identity"],"external_construct":removed["external_construct"],
        "proposed_requirement":removed["requirement"],"guard_type":"FORGE_SAME_ZONE",
        "review_question":"Was it correct for extractor 0.2.1 to suppress this exact Forge action occurrence as zone_transition evidence?",
        "removed_occurrence":removed,"card":card_payload,
        "evidence":{
            "action_type":chosen["action_type"],"action_occurrence_index":chosen["occurrence_index"],
            "action_local_parameters":chosen["parameters"],"Origin":chosen["parameters"].get("Origin",[]),
            "Destination":chosen["parameters"].get("Destination",[]),
            "ValidTgts":chosen["parameters"].get("ValidTgts",[]),"ValidCards":chosen["parameters"].get("ValidCards",[]),
            "Defined":chosen["parameters"].get("Defined",[]),"ChangeType":chosen["parameters"].get("ChangeType",[]),
            "ChangeNum":chosen["parameters"].get("ChangeNum",[]),"LibraryPosition":chosen["parameters"].get("LibraryPosition",[]),
            "raw_action_snippet":chosen["raw_action_snippet"],
            "source_record_action_lines":[{**row,"is_removed_occurrence":row["action_type"]==chosen["action_type"] and row["occurrence_index"]==chosen["occurrence_index"]} for row in occurrences],
        },
        "review_protocol":{"reviewer_a_required":True,"reviewer_b_required":True,"blind_second_review":True,"allowed_decisions":sorted(REVIEW_DECISIONS)},
        "review_fields":{"decision":None,"reason":None},
    }
    return sample


def build_xmage_review_item(removed,card,record,usage):
    identity=_identity_key(removed)
    if usage.get("classification")!="IMPORTED_ONLY" or usage.get("executable_mentions")!=0:
        raise ValueError(f"XMage differential item is not deterministically import-only: {identity}")
    source=record.get("completion",record.get("output",miner.all_strings(record)))
    source=source if isinstance(source,str) else "\n".join(miner.flatten_text(source))
    imports=re.findall(r"(?m)^\s*import\s+(?:static\s+)?([\w.*]+)\s*;\s*$",source)
    refs=java_reference_contexts(source,removed["external_construct"])
    if not refs or any(ref["context"]=="EXECUTABLE" for ref in refs):
        raise ValueError(f"XMage import-only evidence references are incomplete or contain executable use: {identity}")
    lines=source.splitlines()
    non_exec=sorted({ref["line"] for ref in refs if ref["context"]!="EXECUTABLE"})
    source_lines=[{"line":number,"text":lines[number-1]} for number in non_exec if 0<number<=len(lines)]
    card_payload=_canonical_card(card)
    old_identity={"oracle_id":removed["oracle_id"],"source":removed["source"],"source_record_identity":removed["source_record_identity"],"external_construct":removed["external_construct"],"requirement":removed["requirement"],"occurrence_index":removed["occurrence_index"]}
    return {
        "differential_sample_id":_sample_id("XMAGE_IMPORT_ONLY",old_identity),"old_occurrence_identity":old_identity,
        "guard_version":"xmage.non_executable_only.v1",
        "oracle_id":removed["oracle_id"],"card_name":removed["card_name"],"source":"xmage",
        "source_record_identity":removed["source_record_identity"],"external_construct":removed["external_construct"],
        "proposed_requirement":removed["requirement"],"guard_type":"XMAGE_IMPORT_ONLY",
        "review_question":"Was it correct for extractor 0.2.1 to suppress this mapped XMage class as semantic evidence for this card?",
        "removed_occurrence":removed,"card":card_payload,
        "evidence":{
            "mapped_class":removed["external_construct"],"mapped_requirement":removed["requirement"],
            "import_lines":[line for line in source_lines if any(ref["line"]==line["line"] and ref["context"]=="IMPORT" for ref in refs)],
            "all_class_name_references":refs,"usage_classification":usage["classification"],
            "executable_context_excerpt":"\n".join(lines[line-1] for line in sorted({r["line"] for r in refs if r["context"]=="EXECUTABLE"}) if 0<line<=len(lines)),
            "non_executable_context_excerpt":source_lines,"source_java":source,
            "imports_detected_by_classifier":usage.get("import_paths",[]),"comment_mentions":usage.get("comment_mentions",0),
            "string_literal_mentions":usage.get("string_literal_mentions",0),"package_mentions":usage.get("package_mentions",0),
        },
        "review_protocol":{"reviewer_a_required":True,"reviewer_b_required":True,"blind_second_review":True,"allowed_decisions":sorted(REVIEW_DECISIONS)},
        "review_fields":{"decision":None,"reason":None},
    }


def _json_bytes(value):
    return (json.dumps(value,ensure_ascii=False,separators=(",",":"))+"\n").encode("utf-8")


def _yaml_bytes(value):
    return yaml.safe_dump(value,sort_keys=False,allow_unicode=True).encode("utf-8")


def _make_outputs(packet,plan,manifest,report):
    packet_bytes=b"".join(_json_bytes(row) for row in packet)
    report_bytes=report.encode("utf-8")
    return {
        OUT/"differential_review_samples.jsonl":packet_bytes,
        ROOT/"differential_review_results.example.yaml":_yaml_bytes({"reviewer_id":"reviewer-a","review_batch_id":REVIEW_BATCH,"decisions":[]}),
        ROOT/"differential_validation_plan.yaml":_yaml_bytes(plan),
        ROOT/"extractor_0_2_1_differential_validation_manifest.yaml":_yaml_bytes(manifest),
        ROOT/"DIFFERENTIAL_REVALIDATION_REPORT.md":report_bytes,
    }


def _make_report(packet_counts,guard_counts,digest,manifest):
    return "\n".join([
        "# Phase 0.2C.2 — Extractor 0.2.1 Differential Revalidation Packet", "",
        "## Scope", "",
        f"Extractor 0.2.1, parent 0.2.0. Pinned sources: Scryfall `{SOURCE_SET['scryfall']}`, Forge `{SOURCE_SET['forge']}`, XMage `{SOURCE_SET['xmage']}`. Mapping SHA-256 `{manifest['mapping_sha256']}`.",
        "This phase generates an exhaustive blind review packet for the 0.2.0 → 0.2.1 removed evidence set. It does not change extraction or review decisions.", "",
        "## Parent validation", "",
        "Parent validation remains tied to extractor 0.2.0, review batch `phase-0.2a-batch-1`: 460 primary samples, 455 final CORRECT, and 5 final WRONG. Historical labels and intervals are unchanged.", "",
        "## Changed occurrence population", "",
        f"Removed evidence occurrences: {packet_counts['total']}; added: {packet_counts['added']}. Full changed population is covered (sampling fraction 1.0). Guard split: Forge same-zone {guard_counts['FORGE_SAME_ZONE']}, XMage non-executable import-only {guard_counts['XMAGE_IMPORT_ONLY']}. Because this is a census of all changed occurrences, no Wilson or hypergeometric interval applies; if all removals are accepted the result is reported as 104/104 reviewed and accepted, not sampled precision.", "",
        "## Forge removals", "",
        f"All {guard_counts['FORGE_SAME_ZONE']} Forge items identify the exact action type and per-token action occurrence, action-local parameters, raw action line, and sibling action lines from that record. Review asks whether suppressing that one occurrence is correct.", "",
        "## XMage removals", "",
        f"All {guard_counts['XMAGE_IMPORT_ONLY']} XMage items contain the mapped class's import lines, every source reference with context and line number, the executable-context excerpt, canonical card text, and full source Java. Review asks whether the non-executable-only evidence is correctly suppressed.", "",
        "## Review packet", "",
        f"`data/output/differential_review_samples.jsonl` contains {packet_counts['total']} unique items: Reviewer A required on all {packet_counts['total']}, Reviewer B required blind on all {packet_counts['total']}. Decisions are blank. Allowed labels are `REMOVAL_CORRECT`, `REMOVAL_WRONG`, `AMBIGUOUS`, and `SOURCE_EVIDENCE_INSUFFICIENT`.", "",
        "## Unchanged candidate identity proof", "",
        f"Recomputed unchanged-set digest: `{digest}`. It matches the Phase 0.2C.1 old and new unchanged-set digest. The unchanged candidate identity set is eligible for later validation transfer only by exact occurrence identity.", "",
        "## Validation-transfer rule", "",
        "Transfer Phase 0.2B evidence only for occurrence identities proven unchanged. Removed occurrences require this differential review; card name, Requirement, or pattern-name similarity alone is not enough. 0.2.1 added no candidates, so the new-candidate validation population is zero.", "",
        "## Why full 460-sample re-review is unnecessary", "",
        "The 455 previously accepted sample paths remain unchanged, the complete unchanged candidate identity set has the same digest in old/new sets, and extractor 0.2.1 adds no candidate occurrences. The validation delta is the exact set of 104 removed occurrences. This does not transfer 0.2.0 confidence intervals to 0.2.1.", "",
        "## Conditions for extractor 0.2.1 validation", "",
        "All 104 removals must be reviewed by both blind reviewers; all disagreements must be adjudicated; no unresolved wrong-removal or ambiguous guard issue may remain; unchanged-set identity proof must still match; and added candidates must remain zero. Any `REMOVAL_WRONG` means the corresponding guard is not fully validated and the affected 0.2.1 evidence cannot receive clean transferred validation.", "",
        "## Next human-review step", "",
        "Give `differential_review_results.example.yaml` as the format template. Export the canonical JSONL packet to Reviewer A and Reviewer B separately; do not expose A's result file to B. Record decisions in separate YAML files using the stable `differential_sample_id`. No review answers, agreement statistics, precision, or eligibility decisions are present yet.", "",
    ])


def generate():
    diff=json.loads(DIFF_PATH.read_text(encoding="utf-8"))
    manifest_021=yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    validation_021=manifest_021.get("validation_scope",{})
    if validation_021.get("extractor_version")!="0.2.1" or validation_021.get("source_set")!=dict(miner.PINNED_REVISIONS) or validation_021.get("mapping_sha256")!=manifest_021.get("mapping_sha256"):
        raise ValueError("Phase 0.2C.1 extractor/source/mapping scope mismatch")
    if diff.get("old_extractor_version")!="0.2.0" or diff.get("new_extractor_version")!="0.2.1" or diff.get("source_set")!=dict(miner.PINNED_REVISIONS):
        raise ValueError("Differential artifact does not match the pinned extractor transition")
    if diff.get("removed_occurrence_count")!=EXPECTED_REMOVED or diff.get("added_occurrence_count")!=0:
        raise ValueError("Differential population differs from expected 104 removals and zero additions")

    old_rows=list(jsonl(OUT/"requirement_candidates_0_2_0.jsonl"))
    new_rows=list(jsonl(OUT/"requirement_candidates.jsonl"))
    old_set=candidate_occurrences(old_rows);new_set=candidate_occurrences(new_rows)
    removed=old_set.keys()-new_set.keys()
    unchanged=old_set.keys()-removed
    digest=hashlib.sha256("\n".join(json.dumps(list(k),ensure_ascii=False,separators=(",",":")) for k in sorted(unchanged)).encode()).hexdigest()
    if digest!=UNCHANGED_DIGEST or digest!=diff.get("unchanged_candidate_identity_sha256") or digest!=manifest_021.get("differential",{}).get("unchanged_candidate_identity_sha256"):
        raise ValueError(f"Unchanged candidate identity digest mismatch: {digest}")
    diff_items={_identity_key(row):row for row in diff["removed_occurrences"]}
    actual_diff_keys={tuple(key) for key in removed}
    if actual_diff_keys!=set(diff_items):
        raise ValueError("Recomputed old-minus-new evidence set does not exactly match the saved differential artifact")
    if new_set.keys()-old_set.keys(): raise ValueError("Extractor 0.2.1 added candidates; packet generation is blocked")

    mapping=yaml.safe_load((ROOT/"mappings.yaml").read_text(encoding="utf-8"))
    mapping_sha=sha256_file(ROOT/"mappings.yaml")
    if mapping_sha!=manifest_021["mapping_sha256"]: raise ValueError("Current mapping SHA differs from differential manifest")
    forge_removed=[r for r in diff["removed_occurrences"] if r["source"]=="forge"]
    xmage_removed=[r for r in diff["removed_occurrences"] if r["source"]=="xmage"]
    counts={"FORGE_SAME_ZONE":len(forge_removed),"XMAGE_IMPORT_ONLY":len(xmage_removed)}
    if counts!=EXPECTED_BY_GUARD: raise ValueError(f"Removed population partitions are wrong: {counts}")

    # Load only the pinned, cached source snapshots; source-record row IDs use the miner's split order.
    rows=miner.dataset_rows(miner.load_sources())
    scryfall=[r for split in rows["scryfall"].values() for r in split]
    forge=[r for split in rows["forge"].values() for r in split]
    xmage=[r for split in rows["xmage"].values() for r in split]
    card_by_oracle={str(r["oracle_id"]):r for r in scryfall if r.get("oracle_id")}
    same_zone_rows=list(jsonl(OUT/"forge_same_zone_occurrences.jsonl"))
    same_zone_event_map={}
    # Per-action source metadata from the pinned 0.2C audit is matched to the diff occurrence.
    for row in same_zone_rows:
        source_id=row["source_record_identity"]
        index=_record_index(source_id)
        all_actions=forge_action_occurrences(forge[index])
        exact=[a for a in all_actions if a["action_type"]==row["action_type"] and a["raw_action_snippet"]==row["raw_action_snippet"]]
        if not exact: raise ValueError(f"Census Forge action line cannot be found in pinned source row {source_id}")
        # Parameters on duplicate identical lines are identical; each occurrence index is preserved below.
        same_zone_event_map.setdefault((source_id,row["action_type"],row["raw_action_snippet"]),row)

    xmage_usage={(r["source_record_identity"],r["mapped_class"]):r for r in jsonl(OUT/"xmage_usage_census.jsonl")}
    samples=[];seen_ids=set();covered=set()
    removed_multiset=Counter()
    for row in diff["removed_occurrences"]:
        key=_identity_key(row)
        source=row["source"]
        oid=str(row["oracle_id"])
        card=card_by_oracle.get(oid)
        if card is None: raise ValueError(f"Removed Oracle identity is missing in pinned Scryfall corpus: {oid}")
        rid=row["source_record_identity"]
        record_index=_record_index(rid)
        guard_type="FORGE_SAME_ZONE" if source=="forge" else "XMAGE_IMPORT_ONLY"
        if guard_type=="FORGE_SAME_ZONE":
            if record_index>=len(forge): raise ValueError(f"Forge source row index out of range: {rid}")
            source_record=forge[record_index]
            occurrences=forge_action_occurrences(source_record)
            matching=[a for a in occurrences if a["action_type"]==row["external_construct"] and a["occurrence_index"]==row["occurrence_index"]]
            if len(matching)!=1: raise ValueError(f"Removed Forge occurrence not unique in source script: {key}")
            selected=matching[0]
            if selected["parameters"].get("Origin")!=["Library"] or selected["parameters"].get("Destination")!=["Library"]:
                raise ValueError(f"Forge removed action is not a same-library action from the pinned census: {key}")
            if (rid,row["external_construct"],selected["raw_action_snippet"]) not in same_zone_event_map:
                raise ValueError(f"Removed Forge action is absent from Phase 0.2C same-zone census: {key}")
            item=build_forge_review_item(row,card,source_record,occurrences)
        else:
            if record_index>=len(xmage): raise ValueError(f"XMage source row index out of range: {rid}")
            source_record=xmage[record_index]
            usage_row=xmage_usage.get((rid,row["external_construct"]))
            if not usage_row or usage_row.get("classification")!="IMPORTED_ONLY" or not usage_row.get("extracted_by_v0_2_0"):
                raise ValueError(f"Removed XMage occurrence is absent from Phase 0.2C import-only census: {key}")
            source_java=source_record.get("completion",source_record.get("output",miner.all_strings(source_record)))
            source_java=source_java if isinstance(source_java,str) else "\n".join(miner.flatten_text(source_java))
            imports=re.findall(r"(?m)^\s*import\s+(?:static\s+)?([\w.*]+)\s*;",source_java)
            classification=miner.classify_java_class_usage(source_java,row["external_construct"],imports=imports)
            if classification["classification"]!="IMPORTED_ONLY" or classification["executable_mentions"]:
                raise ValueError(f"Pinned XMage record no longer classifies as import-only: {key}")
            item=build_xmage_review_item(row,card,source_record,classification)
        sid=item["differential_sample_id"]
        if sid in seen_ids: raise ValueError(f"Duplicate differential sample ID {sid}")
        seen_ids.add(sid);covered.add(key);removed_multiset[key]+=1;samples.append(item)
    if len(samples)!=EXPECTED_REMOVED or len(seen_ids)!=EXPECTED_REMOVED or covered!=set(diff_items) or any(v!=1 for v in removed_multiset.values()):
        raise ValueError(f"Packet coverage invalid: samples={len(samples)}, ids={len(seen_ids)}, covered={len(covered)}, removals={len(diff_items)}")
    if {r["guard_type"] for r in samples if r["source"]=="forge"}!={"FORGE_SAME_ZONE"} or {r["guard_type"] for r in samples if r["source"]=="xmage"}!={"XMAGE_IMPORT_ONLY"}:
        raise ValueError("Review packet guard partition is not one-to-one with source")

    packet_counts={"total":len(samples),"added":diff["added_occurrence_count"],"sampling_fraction":1.0}
    parent_validation=yaml.safe_load((ROOT/"validation_results.yaml").read_text(encoding="utf-8"))
    if parent_validation.get("validation_scope",{}).get("extractor_version")!="0.2.0" or parent_validation.get("review_batch_id")!="phase-0.2a-batch-1" or parent_validation.get("primary_final_counts")!={"CORRECT":455,"WRONG":5}:
        raise ValueError("Historical Phase 0.2B validation linkage differs from expected 0.2.0 result")

    plan={
        "plan_id":"phase-0.2c-2-validation-transfer-v1","review_batch_id":REVIEW_BATCH,
        "extractor_version":"0.2.1","parent_extractor_version":"0.2.0",
        "validation_scope":{"extractor_version":"0.2.1","source_set":dict(SOURCE_SET),"mapping_sha256":mapping_sha},
        "parent_validation":{"extractor_version":"0.2.0","review_batch_id":"phase-0.2a-batch-1","primary_samples":460,"final_correct":455,"final_wrong":5},
        "changed_population":{"removed_occurrences":len(samples),"added_occurrences":diff["added_occurrence_count"],"sampling_fraction":1.0,"by_guard":counts},
        "transfer_rule":{"unit":"canonical mapped evidence occurrence identity: oracle_id + source + source_record_identity + external_construct + requirement + occurrence_index","eligible":"Transfer parent evidence only when that exact occurrence identity is present in both 0.2.0 and 0.2.1 unchanged sets, whose SHA-256 digest is verified.","ineligible":"Removed occurrences require the 0.2C.2 two-review census. Added occurrences require new validation; current added population is zero.","forbidden_shortcuts":["card-only transfer","Requirement-name transfer","pattern-name-only transfer"]},
        "review_policy":{"reviewer_a_items":len(samples),"reviewer_b_items":len(samples),"blind_second_review":True,"decisions":sorted(REVIEW_DECISIONS),"no_precision_intervals_for_census":True},
        "completion_criteria":["All 104 removals reviewed by A and B independently.","All disagreements adjudicated.","No unresolved REMOVAL_WRONG or guard ambiguity remains.","Unchanged-set digest still matches.","Added candidate population remains zero."],
        "on_removal_wrong":"The affected guard is not validated; do not transfer clean 0.2.1 validation to that guard or reinterpret it as a parent mapping error.",
        "status":{"removal_review_complete":False,"validation_transfer_complete":False,"extractor_0_2_1_validation_status":"AWAITING_DIFFERENTIAL_REVIEW","new_precision_calculated":False},
    }
    manifest={
        "extractor_version":"0.2.1","parent_extractor_version":"0.2.0","review_batch_id":REVIEW_BATCH,
        "validation_scope":{"extractor_version":"0.2.1","source_set":dict(SOURCE_SET),"mapping_sha256":mapping_sha},
        "source_set":dict(SOURCE_SET),"mapping_sha256":mapping_sha,
        "parent_validation":{"extractor_version":"0.2.0","review_batch_id":"phase-0.2a-batch-1","primary_samples":460,"final_correct":455,"final_wrong":5},
        "changed_population":{"removed":len(samples),"added":diff["added_occurrence_count"],"sampling_fraction":1.0},
        "removed_by_guard":counts,
        "unchanged_identity":{"match":True,"digest":digest,"old_digest":digest,"new_digest":digest},
        "review_status":{"reviewer_a":"NOT_STARTED","reviewer_b":"NOT_STARTED","adjudication":"NOT_STARTED","reviewer_a_required":len(samples),"reviewer_b_required":len(samples)},
        "validation_transfer":{"unchanged_candidates_eligible":True,"removed_candidates_require_review":True,"new_candidates":diff["added_occurrence_count"],"phase_0_2b_scope_inherited":False,"precision_recalculated":False},
    }
    report=_make_report(packet_counts,counts,digest,manifest)
    first=_make_outputs(samples,plan,manifest,report)
    second=_make_outputs(samples,plan,manifest,report)
    if any(first[path]!=second[path] for path in first): raise ValueError("Differential packet artifacts are nondeterministic")
    for path,content in second.items(): Path(path).write_bytes(content)
    sample_ids={s["differential_sample_id"] for s in samples}
    stats={"total_audited":len(samples),"by_source":{"forge":len(forge_removed),"xmage":len(xmage_removed)},"by_guard":counts,"actions":{"reviewer_a_required":len(samples),"reviewer_b_required":len(samples)},"duplicate_differential_sample_ids":len(samples)-len(sample_ids),"missing_removed_occurrences":len(set(diff_items)-covered),"extra_review_items":len(covered-set(diff_items)),"unchanged_identity_digest":digest,"review_status":"AWAITING_DIFFERENTIAL_REVIEW"}
    miner.write_json(OUT/"differential_review_packet_stats.json",stats)
    return {"samples":samples,"plan":plan,"manifest":manifest,"report":report,"stats":stats,"deterministic":True}


def main():
    parser=argparse.ArgumentParser(description="Create exhaustive blind review packet for 0.2.1 differential removals")
    parser.parse_args()
    result=generate()
    print(json.dumps({"status":"READY_FOR_REVIEW","items":result["stats"]["total_audited"],"by_guard":result["stats"]["by_guard"],"unchanged_digest":result["stats"]["unchanged_identity_digest"],"deterministic":result["deterministic"]},sort_keys=True))


if __name__=="__main__": main()
