"""Build the deterministic extractor 0.2.1 card -> Requirement evidence read model."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from src import cap_miner as miner
from src.differential_review_packet import forge_action_occurrences
from src.guard_differential import candidate_occurrences, jsonl, sha256_file

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"output"
SOURCE_SET=dict(miner.PINNED_REVISIONS)
EXPECTED_MAPPING_SHA="3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a"
TRANSFER_DIGEST="07335ad502e4512712de0af6e4d8cd7fb0322d0a49952fc9826c8cc66b20c36f"
CARD_OUTPUT=OUT/"card_requirement_evidence.jsonl"
PROFILE_OUTPUT=ROOT/"requirement_evidence_projection.yaml"
MANIFEST_OUTPUT=ROOT/"requirement_evidence_projection_manifest.yaml"
REPORT_OUTPUT=ROOT/"REQUIREMENT_EVIDENCE_PROJECTION_REPORT.md"
REVIEWED_JOIN_DECISIONS=ROOT/"reviewed_join_decisions.yaml"


def occurrence_identity(oracle_id,source,source_record_identity,token,requirement,occurrence_index):
    parts={"oracle_id":str(oracle_id),"source":source,"source_record_identity":source_record_identity,"external_construct":token,"requirement_id":requirement,"occurrence_index":int(occurrence_index)}
    payload=json.dumps(parts,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return {"version":1,"id":"evidence-occurrence:"+hashlib.sha256(payload.encode("utf-8")).hexdigest(),"components":parts}


def pair_evidence_status(sources):
    sources=set(sources)
    if sources=={"forge"}: return "FORGE_ONLY"
    if sources=={"xmage"}: return "XMAGE_ONLY"
    if sources=={"forge","xmage"}: return "MULTI_SOURCE_EVIDENCE"
    return "NO_EVIDENCE"


def card_evidence_status(requirement_sources,unmapped_present,source_warning_present=False):
    source_set=set().union(*(set(s) for s in requirement_sources)) if requirement_sources else set()
    if not source_set:
        return "UNRESOLVED" if unmapped_present or source_warning_present else "NO_EVIDENCE"
    if unmapped_present:
        return "PARTIAL_REQUIREMENT_EVIDENCE"
    return "MULTI_SOURCE_EVIDENCE" if len(source_set)>1 else "SINGLE_SOURCE_EVIDENCE"


def _read_mapping_sha():
    sha=sha256_file(ROOT/"mappings.yaml")
    if sha!=EXPECTED_MAPPING_SHA: raise ValueError(f"Mapping SHA changed: {sha}")
    return sha


def _validate_scopes(mapping_sha,manifest,transfer,validation):
    if miner.EXTRACTOR_VERSION!="0.2.1": raise ValueError(f"Expected extractor 0.2.1, got {miner.EXTRACTOR_VERSION}")
    if dict(miner.PINNED_REVISIONS)!=SOURCE_SET: raise ValueError("Pinned dataset revisions differ from projection scope")
    scope=manifest.get("validation_scope",{})
    if manifest.get("status")!="DIFFERENTIAL_VALIDATION_COMPLETE" or scope.get("extractor_version")!="0.2.1" or scope.get("source_set")!=SOURCE_SET or scope.get("mapping_sha256")!=mapping_sha:
        raise ValueError("Extractor 0.2.1 differential-validation manifest is invalid or out of scope")
    if transfer.get("status")!="DIFFERENTIAL_VALIDATION_COMPLETE" or transfer.get("extractor_version")!="0.2.1" or transfer.get("unchanged_identity",{}).get("digest")!=TRANSFER_DIGEST or not transfer.get("unchanged_identity",{}).get("match"):
        raise ValueError("Extractor 0.2.1 validation-transfer artifact is invalid")
    parent_scope=validation.get("validation_scope",{})
    if parent_scope.get("extractor_version")!="0.2.0" or parent_scope.get("mapping_sha256")!=mapping_sha or parent_scope.get("source_set")!=SOURCE_SET:
        raise ValueError("Historical 0.2B validation scope changed or is inconsistent")
    if validation.get("status")!="REVIEW_COMPLETE" or validation.get("primary_final_counts")!={"CORRECT":455,"WRONG":5}:
        raise ValueError("Historical Phase 0.2B validation results are not the expected completed record")


def _source_row_identity(source,revision,index):
    return miner.reviewable_record_identity(source,revision,index)


def _validation_catalog(plan,results,transfer):
    result_by_id={row["pattern_id"]:row for row in results.get("pattern_results",[])}
    transfer_rows=transfer.get("transfer",{}).get("pattern_transfer",transfer.get("pattern_transfer",[]))
    transfer_by_id={row["pattern_id"]:row for row in transfer_rows}
    direct={};cross=[]
    for pattern in plan.get("patterns",[]):
        if pattern.get("source") in {"forge","xmage"}:
            key=(pattern["source"],pattern["external_construct"],pattern["proposed_requirement"])
            if key in direct: raise ValueError(f"Duplicate source validation pattern mapping {key}")
            direct[key]=pattern["pattern_id"]
        elif pattern.get("source")=="cross":
            cross.append(pattern)
    return direct,cross,result_by_id,transfer_by_id


def _historical_pattern_metadata(pattern_id,result_by_id,transfer_by_id,validation_scope):
    result=result_by_id.get(pattern_id)
    transfer=transfer_by_id.get(pattern_id)
    if result is None:
        return {"status":"UNREVIEWED","historical_validation":None,"extractor_0_2_1_population_status":transfer.get("population_change") if transfer else "NOT_VALIDATED"}
    interval={"method":result.get("interval_method"),"confidence_level":result.get("confidence_level"),"lower":result.get("lower"),"upper":result.get("upper")}
    historical={
        "status":result.get("validation_status","REVIEW_COMPLETE"),
        "scope":{"extractor_version":validation_scope.get("extractor_version"),"mapping_sha256":validation_scope.get("mapping_sha256"),"source_set":validation_scope.get("source_set")},
        "historical_precision_estimate":result.get("precision_estimate"),"historical_interval":interval,
        "probability_sample_size":result.get("probability_sample_size"),"population_size":result.get("population_size"),
    }
    return {"status":"REVIEW_COMPLETE","historical_validation":historical,"extractor_0_2_1_population_status":transfer.get("population_change") if transfer else "NOT_IN_TRANSFER_PLAN"}


def _join_warning_catalog(decisions,audit):
    audit_by_id={row["audit_id"]:row for row in audit.get("records",[])}
    result=defaultdict(list)
    for decision in decisions:
        if decision.get("action")!="KEEP_WITH_FLAG": continue
        source=decision["source"];oid=str(decision["oracle_id"])
        audit_row=audit_by_id.get(decision["audit_id"],{})
        index=audit_row.get("source_record_index")
        source_id=_source_row_identity(source,SOURCE_SET[source],index) if index is not None else None
        result[oid].append({"source":source,"status":"KEEP_WITH_FLAG","result":decision.get("result"),"reason":decision.get("reason"),"source_record_identity":source_id,"audit_id":decision.get("audit_id")})
    return {oid:sorted(rows,key=lambda r:(r["source"],r.get("source_record_identity") or "")) for oid,rows in result.items()}


def _context_for_occurrence(evidence,forge_rows,xmage_rows,forge_action_cache,xmage_cache):
    source=evidence["source"];index=evidence["source_record_index"];token=evidence["token"]
    if source=="forge":
        cache_key=(index,token,evidence["occurrence_index"])
        if cache_key not in forge_action_cache:
            rid=_source_row_identity("forge",SOURCE_SET["forge"],index)
            record=forge_rows[index]
            actions=forge_action_occurrences(record)
            found=[a for a in actions if a["action_type"]==token and a["occurrence_index"]==evidence["occurrence_index"]]
            if len(found)!=1: raise ValueError(f"Active Forge evidence occurrence does not resolve uniquely to source script: {cache_key}")
            forge_action_cache[cache_key]={"source_record_identity":rid,"action_local_parameters":found[0]["parameters"],"raw_action_snippet":found[0]["raw_action_snippet"]}
        return dict(forge_action_cache[cache_key])
    cache_key=(index,token)
    if cache_key not in xmage_cache:
        rid=_source_row_identity("xmage",SOURCE_SET["xmage"],index)
        record=xmage_rows[index]
        java=record.get("completion",record.get("output",miner.all_strings(record)))
        java=java if isinstance(java,str) else "\n".join(miner.flatten_text(java))
        usage=miner.classify_java_class_usage(java,token)
        if usage.get("non_executable_only") or usage.get("classification")=="IMPORTED_ONLY":
            raise ValueError(f"Suppressed non-executable XMage class leaked into active projection: {cache_key}")
        xmage_cache[cache_key]={"source_record_identity":rid,"java_usage_classification":usage["classification"],"java_excerpt":miner.java_review_excerpt(java,{token}),"import_paths_for_class":usage.get("import_paths",[])}
    return dict(xmage_cache[cache_key])


def _make_occurrence(card,evidence,requirement_id,path_profiles,source_rows,context_caches,warning_by_source_id,unchanged_keys):
    source=evidence["source"];token=evidence["token"];idx=evidence["source_record_index"];occ_index=evidence["occurrence_index"]
    rid=_source_row_identity(source,SOURCE_SET[source],idx)
    key=(str(card["oracle_id"]),source,rid,token,requirement_id,int(occ_index))
    if key not in unchanged_keys:
        raise ValueError(f"Active 0.2.1 evidence identity is not in the exact unchanged candidate set: {key}")
    path_id=f"{source}:{token}->{requirement_id}"
    profile=path_profiles[path_id]
    context=_context_for_occurrence(evidence,source_rows["forge"],source_rows["xmage"],*context_caches)
    warning=warning_by_source_id.get((str(card["oracle_id"]),source,rid))
    return {
        "source":source,"source_revision":SOURCE_SET[source],"source_record_identity":rid,
        "external_construct":token,"requirement_id":requirement_id,"evidence_path_id":path_id,
        "occurrence_index":int(occ_index),"occurrence_identity":occurrence_identity(card["oracle_id"],source,rid,token,requirement_id,occ_index),
        "extractor_version":"0.2.1","mapping_sha256":EXPECTED_MAPPING_SHA,
        "source_match_method":evidence.get("match_method"),"oracle_text_comparison":evidence.get("oracle_text_comparison"),
        "historical_validation_pattern_ids":profile["validation_pattern_ids"],
        "occurrence_transfer":{"status":"TRANSFERRED_UNCHANGED","identity_proof_digest":TRANSFER_DIGEST,"parent_extractor_version":"0.2.0"},
        "join_warning":warning,
        **context,
    }


def _requirement_profile_catalog(mapping,validation_lookup,cross_patterns):
    by_requirement=defaultdict(list)
    path_profiles={}
    for source in ("forge","xmage"):
        for token,requirement in sorted(mapping.get(source,{}).items()):
            path_id=f"{source}:{token}->{requirement}"
            pattern_id=validation_lookup[0].get((source,token,requirement))
            metadata=_historical_pattern_metadata(pattern_id,validation_lookup[2],validation_lookup[3],validation_lookup[4]) if pattern_id else {"status":"UNREVIEWED","historical_validation":None,"extractor_0_2_1_population_status":"NOT_VALIDATED"}
            path={"evidence_path_id":path_id,"source":source,"external_construct":token,"requirement_id":requirement,"validation_pattern_ids":[pattern_id] if pattern_id else [],**metadata,"active_card_requirement_pairs":0,"active_occurrences":0}
            path_profiles[path_id]=path;by_requirement[requirement].append(path)
    cross_profiles={}
    for pattern in cross_patterns:
        pid=pattern["pattern_id"];req=pattern["proposed_requirement"]
        cross_profiles[pid]={"pattern_id":pid,"role":"CROSS_IMPLEMENTATION_CORROBORATION","requirement_id":req,"external_constructs":pattern["external_constructs"],**_historical_pattern_metadata(pid,validation_lookup[2],validation_lookup[3],validation_lookup[4]),"active_card_requirement_pairs":0}
    return by_requirement,path_profiles,cross_profiles


def _project_card(card,candidate,warning_rows,mapping,profiles,cross_profiles,source_rows,caches,unchanged_keys,metrics):
    oid=str(card["oracle_id"])
    unresolved=[];requirements=[];all_sources=set();requirement_sources=[]
    candidate=candidate or {}
    warnings=warning_rows.get(oid,[])
    for item in candidate.get("unmapped_evidence",[]):
        source=item["source"];index=item.get("source_record_index")
        unresolved.append({**item,"source_revision":SOURCE_SET.get(source),"source_record_identity":_source_row_identity(source,SOURCE_SET[source],index) if source in SOURCE_SET and index is not None else None,"kind":"UNMAPPED_EXTERNAL_CONSTRUCT"})
    if warnings:
        unresolved.extend({"kind":"SOURCE_JOIN_WARNING",**row} for row in warnings)
    for requirement in candidate.get("requirements",[]):
        req_id=requirement["kind"];grouped=defaultdict(list);sources=set()
        for evidence in requirement.get("evidence",[]):
            occurrence=_make_occurrence(card,evidence,req_id,profiles,source_rows,caches,warning_by_source_id=metrics["warning_by_source_id"],unchanged_keys=unchanged_keys)
            grouped[occurrence["evidence_path_id"]].append(occurrence);sources.add(occurrence["source"]);all_sources.add(occurrence["source"])
        if not sources: raise ValueError(f"Projected Requirement lacks active mapped evidence: {oid} {req_id}")
        status=pair_evidence_status(sources)
        if requirement.get("implementation_evidence")!=miner.implementation_status(sources):
            raise ValueError(f"Implementation evidence mismatch on {oid}/{req_id}: stored={requirement.get('implementation_evidence')}, computed={status}")
        path_rows=[]
        for path_id,occurrences in sorted(grouped.items()):
            profile=profiles[path_id];profile["active_occurrences"]+=len(occurrences);profile["active_card_requirement_pairs"]+=1
            metrics["active_path_ids"].add(path_id)
            (metrics["validated_path_ids"] if profile["status"]=="REVIEW_COMPLETE" else metrics["unreviewed_path_ids"]).add(path_id)
            path_rows.append({**profile,"occurrences":occurrences})
        matching_cross=[]
        if sources=={"forge","xmage"}:
            active_paths=set(grouped)
            for pid,cross in sorted(cross_profiles.items()):
                if cross["requirement_id"]!=req_id: continue
                needed={f"{path['source']}:{path.get('token') or path.get('class')}->{req_id}" for path in cross["external_constructs"]}
                if needed<=active_paths:
                    cross["active_card_requirement_pairs"]+=1
                    if cross["status"]=="REVIEW_COMPLETE": metrics["validated_cross"].add(pid)
                    matching_cross.append({key:value for key,value in cross.items() if key!="active_card_requirement_pairs"})
        requirements.append({
            "requirement_id":req_id,"evidence_status":status,"active_occurrence_count":sum(len(v) for v in grouped.values()),
            "source_set":sorted(sources),"evidence_paths":path_rows,
            "corroboration":{"sources":{"forge":"forge" in sources,"xmage":"xmage" in sources},"status":"FORGE_AND_XMAGE" if sources=={"forge","xmage"} else status,"validated_cross_engine_patterns":matching_cross},
            "unresolved_flags":[],"requirement_precision":None,
        })
        requirement_sources.append(sources)
        metrics["requirement_pairs"]+=1
        metrics["pairs_by_requirement"][req_id]+=1
        metrics["pair_source_status"][status]+=1
        if sources=={"forge","xmage"}: metrics["corroborated_pairs"]+=1
        metrics["active_occurrences"]+=sum(len(v) for v in grouped.values())
    has_unmapped=bool(candidate.get("unmapped_evidence"))
    card_state=card_evidence_status(requirement_sources,has_unmapped,bool(warnings))
    resolution=candidate.get("resolution_status","NO_EXTERNAL_EVIDENCE")
    if not candidate:
        resolution="NO_EXTERNAL_EVIDENCE"
    completeness_notes={
        "NO_EXTERNAL_EVIDENCE":"No exact-joined external implementation evidence is currently present; this is not evidence that the card lacks a capability.",
        "FULLY_UNRESOLVED":"Exact-joined external evidence exists, but no extracted construct maps to a current seed Requirement.",
        "PARTIALLY_RESOLVED":"At least one mapped Requirement coexists with one or more unmapped extracted constructs.",
        "COMPLETENESS_UNVERIFIED":"Mapped evidence exists with no observed unmapped token, but lexical extraction does not establish semantic completeness.",
    }
    metrics["cards"]+=1
    if requirements: metrics["cards_with_mapped"]+=1
    else: metrics["cards_with_no_mapped"]+=1
    if unresolved: metrics["cards_with_unresolved"]+=1
    if warnings: metrics["cards_with_source_warning"]+=1
    return {
        "oracle_id":card["oracle_id"],"card_name":card.get("name"),
        "oracle_source":{"type_line":card.get("type_line"),"layout":card.get("layout"),"mana_cost":card.get("mana_cost"),"oracle_text":card.get("oracle_text"),"faces":[{"name":f.get("name"),"type_line":f.get("type_line"),"oracle_text":f.get("oracle_text")} for f in card.get("card_faces") or [] if isinstance(f,dict)]},
        "requirements":sorted(requirements,key=lambda r:r["requirement_id"]),
        "summary":{"requirement_count":len(requirements),"mapped_requirement_sources":sorted(all_sources),"evidence_status":card_state,"corroborated_requirement_count":sum(r["corroboration"]["status"]=="FORGE_AND_XMAGE" for r in requirements),"unresolved":{"present":bool(unresolved),"count":len(unresolved)},"source_warnings":warnings,"completeness":{"status":resolution,"note":completeness_notes.get(resolution,"Completeness has not been established.")}},
        "unresolved_evidence":unresolved,
    }


def generate_projection(cards,candidate_by_oid,warning_rows,mapping,path_profiles,cross_profiles,source_rows,unchanged_keys,warning_by_source_id,out_path):
    metrics={"cards":0,"cards_with_mapped":0,"cards_with_no_mapped":0,"cards_with_unresolved":0,"cards_with_source_warning":0,"requirement_pairs":0,"corroborated_pairs":0,"active_occurrences":0,"pair_source_status":Counter(),"pairs_by_requirement":Counter(),"active_path_ids":set(),"validated_path_ids":set(),"unreviewed_path_ids":set(),"validated_cross":set(),"warning_by_source_id":warning_by_source_id}
    caches=({}, {})
    seen_oids=set();seen_occurrences=set();seen_candidate_keys=set()
    with Path(out_path).open("w",encoding="utf-8",newline="\n") as output:
        for card in cards:
            oid=card.get("oracle_id")
            if not oid: raise ValueError(f"Scryfall card row lacks oracle_id: {card.get('name')}")
            if oid in seen_oids: raise ValueError(f"Duplicate Scryfall oracle_id in projection source: {oid}")
            seen_oids.add(oid)
            row=_project_card(card,candidate_by_oid.get(str(oid)),warning_rows,mapping,path_profiles,cross_profiles,source_rows,caches,unchanged_keys,metrics)
            for req in row["requirements"]:
                for path in req["evidence_paths"]:
                    for occurrence in path["occurrences"]:
                        ident=occurrence["occurrence_identity"]["id"]
                        if ident in seen_occurrences: raise ValueError(f"Duplicate projected occurrence identity: {ident}")
                        seen_occurrences.add(ident)
                        parts=occurrence["occurrence_identity"]["components"]
                        candidate_key=(parts["oracle_id"],parts["source"],parts["source_record_identity"],parts["external_construct"],parts["requirement_id"],parts["occurrence_index"])
                        if candidate_key in seen_candidate_keys: raise ValueError(f"Duplicate active candidate occurrence key: {candidate_key}")
                        seen_candidate_keys.add(candidate_key)
            output.write(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n")
    metrics["unique_oracle_ids"]=len(seen_oids)
    metrics["unique_occurrence_id_count"]=len(seen_occurrences)
    metrics["pair_source_status"]=dict(sorted(metrics["pair_source_status"].items()))
    metrics["pairs_by_requirement"]=dict(sorted(metrics["pairs_by_requirement"].items()))
    metrics["active_candidate_keys"]=seen_candidate_keys
    metrics["active_path_ids"]=metrics["active_path_ids"]
    metrics["validated_path_ids"]=metrics["validated_path_ids"]
    metrics["unreviewed_path_ids"]=metrics["unreviewed_path_ids"]
    metrics["validated_cross_paths"]=metrics["validated_cross"]
    return metrics


def _evidence_profile_yaml(mapping,profiles,cross_profiles,summary,scope):
    requirements=defaultdict(lambda:{"evidence_paths":{"forge":[],"xmage":[]},"cross_corroboration":[],"active_card_requirement_pairs":0,"active_occurrences":0,"requirement_precision":None})
    for profile in profiles.values():
        req=profile["requirement_id"];source=profile["source"]
        row={key:value for key,value in profile.items() if key!="occurrences"}
        requirements[req]["evidence_paths"][source].append(row)
        requirements[req]["active_occurrences"]+=profile["active_occurrences"]
    for profile in cross_profiles.values():
        req=profile["requirement_id"];requirements[req]["cross_corroboration"].append(profile)
    for req,value in requirements.items():
        value["active_card_requirement_pairs"]=summary["card_requirement_pairs_by_requirement"].get(req,0)
        for source in ("forge","xmage"):
            value["evidence_paths"][source].sort(key=lambda r:r["evidence_path_id"])
        value["cross_corroboration"].sort(key=lambda r:r["pattern_id"])
    return {
        "projection_id":"manafold-cap-miner-requirement-evidence-projection.v1","status":"GENERATED_READ_MODEL_NO_ELIGIBILITY",
        "projection_scope":scope,"numeric_precision_combination":"NONE",
        "semantics":{"forge_and_xmage":"implementation evidence only; not normative rules authority","cross_engine_corroboration":"source presence is not proof of rules correctness and does not increase a numeric score","no_evidence":"no currently extracted mapped evidence; does not mean the card lacks a capability","completeness":"absence of unmapped evidence is not proof of semantic completeness","historical_validation":"pattern review remains scoped to extractor 0.2.0; exact unchanged occurrence identity transfer is recorded separately"},
        "summary":summary,"requirements":{req:requirements[req] for req in sorted(requirements)},
    }


def _render_report(summary,profile,warning_count,unmatched_counts,comparison):
    lines=[
        "# Phase 0.2D — Requirement Evidence Projection", "",
        "## Scope", "",
        f"Extractor `{miner.EXTRACTOR_VERSION}`; pinned Scryfall `{SOURCE_SET['scryfall']}`, Forge `{SOURCE_SET['forge']}`, XMage `{SOURCE_SET['xmage']}`; mapping SHA-256 `{EXPECTED_MAPPING_SHA}`. Projection identity is the Scryfall `oracle_id`.",
        "This deterministic read model lists current mapped Requirement evidence under extractor 0.2.1. It does not modify extraction or mapping semantics.", "",
        "## Projection semantics", "",
        "A card–Requirement pair records active source occurrences and their evidence paths. Forge and XMage remain implementation witnesses, and explicit cross-engine validation patterns remain separate from source corroboration. No evidence means only that no currently extracted mapped evidence was joined to the Oracle identity; it does not mean the real card lacks that capability. `COMPLETENESS_UNVERIFIED` is not a completeness claim.", "",
        "## Input validation scope", "",
        f"Extractor differential validation: `{profile['projection_scope']['differential_validation_status']}`. Exact unchanged occurrence identity transfer is bound to `{TRANSFER_DIGEST}`. Removed occurrences active in projection: {summary['removed_occurrence_intersection']}; added candidates: {summary['added_candidates']}.", "",
        "## Card population", "",
        f"Oracle cards: {summary['total_oracle_cards']:,}. Cards with mapped Requirement evidence: {summary['cards_with_mapped_requirement_evidence']:,}. Cards with no mapped Requirement evidence: {summary['cards_with_no_mapped_requirement_evidence']:,}. Cards with unresolved tokens or source warnings: {summary['cards_with_unresolved_evidence']:,}. {warning_count} historical KEEP_WITH_FLAG join warnings are propagated where their Oracle identities occur.", "",
        "## Requirement population", "",
        f"Generic Requirement identifiers in the current mappings: {summary['distinct_requirements']}. Card–Requirement pairs: {summary['total_card_requirement_pairs']:,}. Active mapped source occurrences: {summary['total_active_mapped_occurrences']:,}. These use separate counting units.", "",
        "## Evidence paths", "",
        f"Distinct active source mapping paths: {summary['active_source_evidence_paths']}. Paths with historical 0.2.0 review metadata: {summary['validated_evidence_paths']}; without a selected review record: {summary['unreviewed_evidence_paths']}. Active occurrences with exact unchanged identity transfer: {summary['transferred_unchanged_occurrences']:,}. Historical pattern precision appears only as scoped metadata in each path profile; it is not recalculated under 0.2.1.", "",
        "## Forge-only evidence", "",
        f"Forge-only card–Requirement pairs: {summary['forge_only_card_requirement_pairs']:,}. Each retains its Forge construct, source record, action-local fields, occurrence identity, join warnings, and validation path metadata where available.", "",
        "## XMage-only evidence", "",
        f"XMage-only card–Requirement pairs: {summary['xmage_only_card_requirement_pairs']:,}. Each retains its mapped class, source record, executable-use classification, excerpt, join warnings, and validation path metadata where available.", "",
        "## Cross-engine corroboration", "",
        f"Card–Requirement pairs with both Forge and XMage source evidence: {summary['multi_source_card_requirement_pairs']:,}. Explicit validated cross-engine paths: {summary['validated_cross_engine_paths']}. Source corroboration alone does not imply rules correctness.", "",
        "## Validated vs unreviewed evidence paths", "",
        "Reviewed mapping paths display their historical 0.2.0 review scope and the 0.2.1 exact-identity transfer status separately. Mappings without an explicit Phase 0.2B pattern remain `UNREVIEWED`. The projection does not infer validation from a similar pattern name.", "",
        "## Unresolved evidence", "",
        f"Cards with unresolved evidence: {summary['cards_with_unresolved_evidence']:,}. Unmapped constructs stay attached to their card identity and source record where known. Exact-unmatched records remain outside card projections rather than being attached by fuzzy name matching. Unmatched source-record counts: Forge {unmatched_counts['unmatched_forge']}, XMage {unmatched_counts['unmatched_xmage']}; ambiguous matching records: {unmatched_counts['ambiguous']}.", "",
        "## Completeness limitations", "",
        "Lexical extraction cannot prove that all semantics were captured. Cards with no mapped evidence may have no joined implementation record, may have only unmapped evidence, or may use unrecognized constructs. No card is declared fully semantically resolved.", "",
        "## Why this is not CAP eligibility", "",
        "The projection is implementation evidence, not Comprehensive Rules truth, card completeness, capability certification, or CAP eligibility. It produces no `CAP_ELIGIBLE` boolean and no Requirement-level combined precision.", "",
        "## Next phase", "",
        "Review the projected evidence schema and counts before defining any separate Requirement-to-CAP ontology work. No rules authority, mapping expansion, SQLite, or Manafold integration was added.", "",
        f"Historical candidate occurrence comparison: extractor 0.2.0 had {comparison['old_occurrences']:,} mapped occurrences; extractor 0.2.1 has {comparison['new_occurrences']:,}; difference {comparison['difference']:+,}.", "",
    ]
    return "\n".join(lines)


def run_projection():
    mapping_sha=_read_mapping_sha()
    transfer=yaml.safe_load((ROOT/"extractor_0_2_1_validation_transfer.yaml").read_text(encoding="utf-8"))
    manifest=yaml.safe_load((ROOT/"extractor_0_2_1_differential_validation_manifest.yaml").read_text(encoding="utf-8"))
    parent_validation=yaml.safe_load((ROOT/"validation_results.yaml").read_text(encoding="utf-8"))
    differential_validation=yaml.safe_load((ROOT/"differential_validation_results.yaml").read_text(encoding="utf-8"))
    _validate_scopes(mapping_sha,manifest,transfer,parent_validation)
    if differential_validation.get("status")!="DIFFERENTIAL_VALIDATION_COMPLETE" or differential_validation.get("extractor_version")!="0.2.1" or differential_validation.get("decisions",{}).get("REMOVAL_CORRECT")!=104 or differential_validation.get("agreement",{}).get("disagreements")!=0:
        raise ValueError("Final extractor 0.2.1 differential review results are not complete")
    differential=json.loads((ROOT/"extractor_0_2_0_to_0_2_1_diff.json").read_text(encoding="utf-8"))
    if differential.get("added_occurrence_count")!=0 or differential.get("removed_occurrence_count")!=104: raise ValueError("Differential artifact population mismatch")
    loaded=miner.dataset_rows(miner.load_sources())
    cards=sorted((r for split in loaded["scryfall"].values() for r in split),key=lambda c:str(c.get("oracle_id") or ""))
    forge_rows=[r for split in loaded["forge"].values() for r in split]
    xmage_rows=[r for split in loaded["xmage"].values() for r in split]
    if len(cards)!=36923 or len({r.get("oracle_id") for r in cards})!=36923 or any(not r.get("oracle_id") for r in cards): raise ValueError("Pinned Scryfall Oracle identity population is not 36,923 unique IDs")
    mapping=yaml.safe_load((ROOT/"mappings.yaml").read_text(encoding="utf-8"))
    candidate_rows=list(jsonl(OUT/"requirement_candidates.jsonl"))
    if any(row.get("provenance",{}).get("extractor_version")!="0.2.1" or row.get("provenance",{}).get("mapping_sha256")!=mapping_sha for row in candidate_rows): raise ValueError("Candidate evidence input is not extractor 0.2.1 under current mapping SHA")
    candidate_by_oid={str(row["oracle_id"]):row for row in candidate_rows}
    if len(candidate_by_oid)!=len(candidate_rows): raise ValueError("Duplicate Oracle IDs in candidate evidence input")
    if not set(candidate_by_oid)<= {str(card["oracle_id"]) for card in cards}: raise ValueError("Candidate evidence references an Oracle ID outside pinned Scryfall")
    old_rows=list(jsonl(OUT/"requirement_candidates_0_2_0.jsonl"))
    old_occurrences=candidate_occurrences(old_rows);new_occurrences=candidate_occurrences(candidate_rows)
    removed=set(old_occurrences)-set(new_occurrences);added=set(new_occurrences)-set(old_occurrences)
    if added: raise ValueError(f"Unexpected new candidate identities: {len(added)}")
    unchanged_old=set(old_occurrences)-removed
    if unchanged_old!=set(new_occurrences): raise ValueError("Current occurrence set does not equal the exact unchanged 0.2.0 set")
    digest=hashlib.sha256("\n".join(json.dumps(list(k),ensure_ascii=False,separators=(",",":")) for k in sorted(unchanged_old)).encode("utf-8")).hexdigest()
    if digest!=TRANSFER_DIGEST or digest!=transfer["unchanged_identity"]["digest"]: raise ValueError(f"Unchanged identity digest mismatch: {digest}")
    removed_identity_keys={tuple((str(row["oracle_id"]),row["source"],row["source_record_identity"],row["external_construct"],row["requirement"],int(row["occurrence_index"]))) for row in differential["removed_occurrences"]}
    if removed_identity_keys!=removed: raise ValueError("Saved differential removals do not exactly equal old-minus-new candidate identity set")

    req_stats=json.loads((OUT/"requirement_stats.json").read_text(encoding="utf-8"))
    stats=json.loads((OUT/"stats.json").read_text(encoding="utf-8"))
    if req_stats["cards"]["scryfall_total"]!=len(cards) or req_stats["requirements"]["total_mapped_candidates"]!=sum(len(r.get("requirements",[])) for r in candidate_rows):
        raise ValueError("Existing requirement statistics do not reconcile with projection inputs")
    join_decisions=yaml.safe_load(REVIEWED_JOIN_DECISIONS.read_text(encoding="utf-8"))
    join_audit=json.loads((OUT/"suspicious_join_audit.json").read_text(encoding="utf-8"))
    warning_rows=_join_warning_catalog(join_decisions,join_audit)
    warning_by_source_id={}
    for oid,rows in warning_rows.items():
        for row in rows:
            if row.get("source_record_identity"):
                warning_by_source_id[(oid,row["source"],row["source_record_identity"])]=row
    if sum(len(rows) for rows in warning_rows.values())!=9: raise ValueError("Expected all nine KEEP_WITH_FLAG source warnings")

    validation_plan=yaml.safe_load((ROOT/"validation_plan.yaml").read_text(encoding="utf-8"))
    direct_lookup,cross_specs,result_by_id,transfer_by_id=_validation_catalog(validation_plan,parent_validation,transfer)
    pattern_transfer_rows=transfer_by_id
    for path_id,metadata in pattern_transfer_rows.items():
        if metadata.get("population_change") not in {"UNCHANGED","REMOVALS_ONLY"}: raise ValueError(f"Unexpected pattern transfer state: {path_id}")
    profiles_by_req,path_profiles,cross_profiles=_requirement_profile_catalog(mapping,(direct_lookup,cross_specs,result_by_id,transfer_by_id,parent_validation["validation_scope"]),cross_specs)

    base_profiles=copy.deepcopy((profiles_by_req,path_profiles,cross_profiles))
    output_path=CARD_OUTPUT
    first_profiles=copy.deepcopy(base_profiles)
    first_metrics=generate_projection(cards,candidate_by_oid,warning_rows,mapping,first_profiles[1],first_profiles[2],{"forge":forge_rows,"xmage":xmage_rows},unchanged_old,warning_by_source_id,output_path)
    active_keys=first_metrics["active_candidate_keys"]
    removed_intersection=active_keys & removed
    if first_metrics["cards"]!=36923 or first_metrics["unique_oracle_ids"]!=36923 or first_metrics["unique_occurrence_id_count"]!=len(new_occurrences):
        raise ValueError(f"Projection coverage does not reconcile: {first_metrics}")
    if first_metrics["active_occurrences"]!=len(new_occurrences) or active_keys!=set(new_occurrences): raise ValueError("Projected active occurrences do not exactly equal the canonical 0.2.1 candidate set")
    if removed_intersection: raise ValueError(f"Removed differential occurrence IDs are active: {len(removed_intersection)}")
    if first_metrics["requirement_pairs"]!=req_stats["requirements"]["total_mapped_candidates"]: raise ValueError("Projected card-Requirement pair count differs from canonical candidate count")

    active_path_ids=first_metrics["active_path_ids"]
    profile_summary={
        "total_oracle_cards":first_metrics["cards"],
        "cards_with_mapped_requirement_evidence":first_metrics["cards_with_mapped"],
        "cards_with_no_mapped_requirement_evidence":first_metrics["cards_with_no_mapped"],
        "cards_with_unresolved_evidence":first_metrics["cards_with_unresolved"],
        "cards_with_join_warnings":first_metrics["cards_with_source_warning"],
        "distinct_requirements":len(set(mapping.get("forge",{}).values())|set(mapping.get("xmage",{}).values())),
        "total_card_requirement_pairs":first_metrics["requirement_pairs"],
        "total_active_mapped_occurrences":first_metrics["active_occurrences"],
        "forge_only_card_requirement_pairs":first_metrics["pair_source_status"].get("FORGE_ONLY",0),
        "xmage_only_card_requirement_pairs":first_metrics["pair_source_status"].get("XMAGE_ONLY",0),
        "multi_source_card_requirement_pairs":first_metrics["pair_source_status"].get("MULTI_SOURCE_EVIDENCE",0),
        "cards_with_both_engines_on_requirement":first_metrics["corroborated_pairs"],
        "active_source_evidence_paths":len(active_path_ids),
        "validated_evidence_paths":len(first_metrics["validated_path_ids"]),
        "unreviewed_evidence_paths":len(first_metrics["unreviewed_path_ids"]),
        "validated_cross_engine_paths":len(first_metrics["validated_cross_paths"]),
        "transferred_unchanged_occurrences":first_metrics["active_occurrences"],
        "removed_occurrence_intersection":len(removed_intersection),
        "added_candidates":len(added),
        "unmapped_forge_occurrences":req_stats["unmapped_evidence"]["forge_tokens"],
        "unmapped_xmage_occurrences":req_stats["unmapped_evidence"]["xmage_tokens"],
        "card_requirement_pairs_by_requirement":first_metrics["pairs_by_requirement"],
        "implementation_pair_partition":first_metrics["pair_source_status"],
    }
    comparison={"old_occurrences":len(old_occurrences),"new_occurrences":len(new_occurrences),"difference":len(new_occurrences)-len(old_occurrences)}
    profile_scope={"extractor_version":"0.2.1","parent_extractor_version":"0.2.0","source_set":SOURCE_SET,"mapping_sha256":mapping_sha,"differential_validation_status":transfer["status"],"unchanged_identity_digest":digest}
    profile_obj=_evidence_profile_yaml(mapping,first_profiles[1],first_profiles[2],profile_summary,profile_scope)
    profile_bytes=yaml.safe_dump(profile_obj,sort_keys=False,allow_unicode=True).encode("utf-8")
    report_text=_render_report(profile_summary,profile_obj,sum(len(v) for v in warning_rows.values()),{"unmatched_forge":stats["unmatched_forge"],"unmatched_xmage":stats["unmatched_xmage"],"ambiguous":stats["ambiguous"]},comparison)
    report_bytes=report_text.encode("utf-8")

    inventory=json.loads((OUT/"inventory.json").read_text(encoding="utf-8"))
    if {key:inventory["datasets"][key].get("revision") for key in SOURCE_SET}!=SOURCE_SET: raise ValueError("Materialized dataset inventory revisions differ from projection scope")
    if {key:inventory["datasets"][key].get("rows") for key in SOURCE_SET}!={"scryfall":36923,"forge":27286,"xmage":18985}: raise ValueError("Pinned dataset row counts differ from expected inventory")
    old_profile_counts=Counter(row["historical_validation"].get("scope",{}).get("extractor_version") for rows in profile_obj["requirements"].values() for source in ("forge","xmage") for row in rows["evidence_paths"][source] if row.get("historical_validation"))
    if old_profile_counts and set(old_profile_counts)!={"0.2.0"}: raise ValueError("Historical evidence-path review metadata has an unexpected extractor scope")
    if len(direct_lookup)!=len(set(direct_lookup)): raise ValueError("Duplicate source validation mapping paths")
    if profile_summary["validated_cross_engine_paths"]>len(cross_specs): raise ValueError("Cross-engine validation path count exceeds explicit plan")

    comparison_sources={"unmatched_forge":stats["unmatched_forge"],"unmatched_xmage":stats["unmatched_xmage"],"ambiguous":stats["ambiguous"]}
    profile_path_ids={path for req in profile_obj["requirements"].values() for source in ("forge","xmage") for path in (r["evidence_path_id"] for r in req["evidence_paths"][source])}
    if not active_path_ids<=profile_path_ids: raise ValueError("An active evidence path has no Requirement profile")

    input_provenance={
        "requirement_candidates_0_2_1_sha256":sha256_file(OUT/"requirement_candidates.jsonl"),
        "requirement_candidates_0_2_0_sha256":sha256_file(OUT/"requirement_candidates_0_2_0.jsonl"),
        "mappings_sha256":mapping_sha,
        "validation_transfer_sha256":sha256_file(ROOT/"extractor_0_2_1_validation_transfer.yaml"),
        "differential_validation_results_sha256":sha256_file(ROOT/"differential_validation_results.yaml"),
    }
    card_sha=sha256_file(CARD_OUTPUT)
    profile_sha=hashlib.sha256(profile_bytes).hexdigest();report_sha=hashlib.sha256(report_bytes).hexdigest()
    manifest={
        "projection_version":1,"extractor_version":"0.2.1","source_set":SOURCE_SET,"mapping_sha256":mapping_sha,
        "validation":{"differential_status":transfer["status"],"validation_transfer_artifact":"extractor_0_2_1_validation_transfer.yaml","parent_pattern_validation_extractor_version":"0.2.0","phase_0_2b_precision_reused_as_0_2_1":False},
        "identity":{"primary_card_identity":"oracle_id","occurrence_identity_version":1,"occurrence_identity_components":["oracle_id","source","source_record_identity","external_construct","requirement_id","occurrence_index"],"unchanged_candidate_identity_digest":digest},
        "projection_counts":profile_summary,"input_provenance":input_provenance,
        "outputs":{"data/output/card_requirement_evidence.jsonl":{"rows":first_metrics["cards"],"sha256":card_sha},"requirement_evidence_projection.yaml":{"sha256":profile_sha},"REQUIREMENT_EVIDENCE_PROJECTION_REPORT.md":{"sha256":report_sha}},
        "limitations":{"cap_eligibility":False,"rules_authority_integrated":False,"requirement_level_combined_precision":False,"sqlite":False},
    }
    manifest_bytes=yaml.safe_dump(manifest,sort_keys=False,allow_unicode=True).encode("utf-8")

    # Run the card serializer a second time into a temporary file and compare the complete read model.
    with tempfile.NamedTemporaryFile(prefix="projection_repeat_",suffix=".jsonl",dir=OUT,delete=False) as temp:
        repeat_path=Path(temp.name)
    try:
        repeat_profiles=copy.deepcopy(base_profiles)
        repeat_metrics=generate_projection(cards,candidate_by_oid,warning_rows,mapping,repeat_profiles[1],repeat_profiles[2],{"forge":forge_rows,"xmage":xmage_rows},unchanged_old,warning_by_source_id,repeat_path)
        if sha256_file(repeat_path)!=card_sha or repeat_metrics["active_candidate_keys"]!=active_keys:
            raise ValueError("Card projection output was nondeterministic")
        repeated_profile=_evidence_profile_yaml(mapping,repeat_profiles[1],repeat_profiles[2],profile_summary,profile_scope)
        if yaml.safe_dump(repeated_profile,sort_keys=False,allow_unicode=True).encode("utf-8")!=profile_bytes:
            raise ValueError("Requirement profile output was nondeterministic")
        if _render_report(profile_summary,repeated_profile,sum(len(v) for v in warning_rows.values()),comparison_sources,comparison).encode("utf-8")!=report_bytes:
            raise ValueError("Projection report output was nondeterministic")
    finally:
        repeat_path.unlink(missing_ok=True)
    if yaml.safe_dump(manifest,sort_keys=False,allow_unicode=True).encode("utf-8")!=manifest_bytes:
        raise ValueError("Projection manifest output was nondeterministic")
    PROFILE_OUTPUT.write_bytes(profile_bytes)
    REPORT_OUTPUT.write_bytes(report_bytes)
    MANIFEST_OUTPUT.write_bytes(manifest_bytes)
    return {"summary":profile_summary,"manifest":manifest,"deterministic":True}


def main():
    parser=argparse.ArgumentParser(description="Build the extractor 0.2.1 card-to-Requirement evidence projection")
    parser.parse_args()
    result=run_projection()
    print(json.dumps({"status":"PROJECTION_COMPLETE","cards":result["summary"]["total_oracle_cards"],"requirement_pairs":result["summary"]["total_card_requirement_pairs"],"active_occurrences":result["summary"]["total_active_mapped_occurrences"],"removed_occurrence_intersection":result["summary"]["removed_occurrence_intersection"],"deterministic":result["deterministic"]},sort_keys=True))


if __name__=="__main__": main()
