"""Deterministic, deliberately small MTG implementation-evidence miner."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import hashlib
import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "output"
SOURCES = {
    "scryfall": "nishtahir/scryfall-oracle-cards",
    "forge": "404NotF0und/MtG-json-to-ForgeScript",
    "xmage": "Frogski/xMageData",
}
PINNED_REVISIONS = {
    "scryfall": "0ce026779dae1a9a6448ef7a85e606d662343f5e",
    "forge": "cef86f363d7f7d5b3293248a75f550a7c3404066",
    "xmage": "6212eb37907c1ce751d8a3fea8b3322056dc0264",
}
EXTRACTOR_VERSION = "0.2.0"
VALIDATION_EXTRACTOR_VERSION = "0.2.0"
REVIEW_DECISIONS = {"CORRECT","TOO_BROAD","TOO_NARROW","CONTEXT_DEPENDENT","WRONG","AMBIGUOUS","SOURCE_EVIDENCE_INSUFFICIENT"}
PHASE_0_2A_SAMPLE_IDS_SHA256 = "feeb4a19ef205df5cb61078e2df8f1ba11f4570b548ac238bd84f59447e93faf"
PHASE_0_2A_LOW_SAMPLE_IDS_SHA256 = "7423edb900b12bbd86242937da295ea66833c0b4dbcafce1c643917c260eac31"
VALIDATION_EXTRACTOR_VERSION = "0.2.0"
REVIEW_DECISIONS = {"CORRECT","TOO_BROAD","TOO_NARROW","CONTEXT_DEPENDENT","WRONG","AMBIGUOUS","SOURCE_EVIDENCE_INSUFFICIENT"}
GENERIC_XMAGE_CLASSES = {
    "Ability", "Effect", "Cost", "Target", "Filter", "Condition",
    "OneShotEffect", "ContinuousEffect", "SimpleActivatedAbility",
    "SimpleStaticAbility", "EntersBattlefieldTriggeredAbility",
    "DiesSourceTriggeredAbility", "TriggeredAbility", "TriggeredAbilityImpl",
    "ReplacementEffectImpl", "ContinuousRuleModifyingEffectImpl",
}


def norm(value: object) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).split())


def select_unambiguous(candidates):
    """Return a unique candidate, or None when zero/multiple exact candidates exist."""
    unique=list(dict.fromkeys(candidates))
    return unique[0] if len(unique)==1 else None


def implementation_status(sources):
    sources=set(sources)
    if sources=={"forge","xmage"}: return "MULTI_IMPLEMENTATION_AGREEMENT"
    if sources=={"forge"}: return "FORGE_ONLY"
    if sources=={"xmage"}: return "XMAGE_ONLY"
    return "NONE"


def exact_oracle_id_match(record, by_id):
    oid=record.get("oracle_id") or record.get("oracleId")
    if not oid or str(oid) not in by_id: return None
    indexes=by_id[str(oid)]
    return (indexes[0],"oracle_id") if len(indexes)==1 else (None,"ambiguous_oracle_id")


def join_audit_id(source, oracle_id):
    return f"{source}:{oracle_id}"


def lookup_join_decision(decisions, audit_id):
    return decisions.get(audit_id)


def apply_join_review(candidate, decision):
    """Return whether evidence may be used and optional review metadata."""
    if candidate is None: return False,None
    if not decision: return True,None
    if decision["action"]=="REJECT_JOIN": return False,None
    return True,{"join_review_status":decision["action"],"join_review_result":decision["result"],"join_review_reason":decision["reason"]}


def join_review_metadata(source, oracle_id, decisions):
    decision=lookup_join_decision(decisions,join_audit_id(source,oracle_id))
    if not decision: return {}
    _,metadata=apply_join_review(0,decision)
    return metadata or {}


def candidate_status_counts(sf, forge_matches, xmage_matches, forge_map, xmage_map):
    counts=Counter()
    for index in set(forge_matches)|set(xmage_matches):
        kinds=defaultdict(set)
        for _,_,actions,_,_,_,_,_ in forge_matches.get(index,[]):
            for token in actions:
                if token in forge_map: kinds[forge_map[token]].add("forge")
        for _,_,_,_,semantic,_,_,_,_ in xmage_matches.get(index,[]):
            for token in semantic:
                if token in xmage_map: kinds[xmage_map[token]].add("xmage")
        for sources in kinds.values():
            counts[implementation_status(sources)]+=1
    return {"total_mapped_candidates":sum(counts.values()),"multi_implementation_agreement":counts["MULTI_IMPLEMENTATION_AGREEMENT"],"forge_only":counts["FORGE_ONLY"],"xmage_only":counts["XMAGE_ONLY"]}


def validate_review_decision(value):
    if value not in REVIEW_DECISIONS: raise ValueError(f"Unknown pattern review decision: {value}")
    return value


def validation_status_from_results(results):
    return "AWAITING_REVIEW" if not results else "REVIEW_RESULTS_PRESENT_AGGREGATION_PENDING"


def wilson_interval(accepted, total, z=1.959963984540054):
    """Return estimate and 95% Wilson bounds; null values when no reviews exist."""
    if total<=0: return {"estimate":None,"reviewed_n":0,"accepted_n":0,"confidence_level":0.95,"interval_method":"wilson","lower":None,"upper":None}
    p=accepted/total; z2=z*z; den=1+z2/total
    center=(p+z2/(2*total))/den
    radius=(z*((p*(1-p)/total+z2/(4*total*total))**0.5))/den
    return {"estimate":p,"reviewed_n":total,"accepted_n":accepted,"confidence_level":0.95,"interval_method":"wilson","lower":max(0.0,center-radius),"upper":min(1.0,center+radius)}


def sampling_fraction(population_n, sample_n):
    return sample_n/population_n if population_n>0 else None


def interval_method_for_population(population_n, sample_n, threshold=0.05):
    fraction=sampling_fraction(population_n,sample_n)
    if fraction is None or sample_n<=0: return "NOT_AVAILABLE"
    return "WILSON_BINOMIAL" if fraction<=threshold else "FINITE_POPULATION_HYPERGEOMETRIC"


def primary_interval_summary(population_n, sample_n, threshold=0.05):
    method=interval_method_for_population(population_n,sample_n,threshold)
    if method=="FINITE_POPULATION_HYPERGEOMETRIC":
        interval=hypergeometric_interval(population_n,sample_n,None)
    else:
        interval={"method":method,"population_n":population_n,"sample_n":sample_n,"accepted_n":None,"confidence_level":0.95,"estimate":None,"lower":None,"upper":None}
    return {"sampling_fraction":sampling_fraction(population_n,sample_n),"planned_interval_method":method,"interval":interval}


def _log_choose(n,k):
    if k<0 or k>n: return float("-inf")
    return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)


def _hypergeometric_tails(population_n,population_successes,sample_n,observed):
    low=max(0,sample_n-(population_n-population_successes));high=min(sample_n,population_successes)
    denom=_log_choose(population_n,sample_n)
    lower=upper=0.0
    for x in range(low,high+1):
        logp=_log_choose(population_successes,x)+_log_choose(population_n-population_successes,sample_n-x)-denom
        probability=math.exp(logp) if logp>-745 else 0.0
        if x<=observed: lower+=probability
        if x>=observed: upper+=probability
    return min(1.0,lower),min(1.0,upper)


def hypergeometric_interval(population_n, sample_n, accepted_n, confidence_level=0.95):
    """Equal-tailed exact inversion for a hypergeometric population proportion."""
    base={"method":"FINITE_POPULATION_HYPERGEOMETRIC","population_n":population_n,"sample_n":sample_n,"accepted_n":accepted_n,"confidence_level":confidence_level,"estimate":None,"lower":None,"upper":None}
    if population_n<0 or sample_n<0 or sample_n>population_n: raise ValueError("Require 0 <= sample_n <= population_n")
    if accepted_n is None: return base
    if accepted_n<0 or accepted_n>sample_n: raise ValueError("accepted_n must be between zero and sample_n")
    if population_n==0: return base
    if sample_n==population_n:
        estimate=accepted_n/population_n
        return {**base,"estimate":estimate,"lower":estimate,"upper":estimate}
    alpha=(1-confidence_level)/2
    plausible=[]
    for successes in range(population_n+1):
        lower_tail,upper_tail=_hypergeometric_tails(population_n,successes,sample_n,accepted_n)
        if lower_tail>=alpha and upper_tail>=alpha: plausible.append(successes)
    if not plausible: return {**base,"estimate":accepted_n/sample_n if sample_n else None}
    return {**base,"estimate":accepted_n/sample_n if sample_n else None,"lower":min(plausible)/population_n,"upper":max(plausible)/population_n}


def empty_interval_for_population(population_n, sample_n, threshold=0.05):
    method=interval_method_for_population(population_n,sample_n,threshold)
    if method=="FINITE_POPULATION_HYPERGEOMETRIC":
        return hypergeometric_interval(population_n,sample_n,None)
    return {"method":method,"population_n":population_n,"sample_n":sample_n,"accepted_n":None,"confidence_level":0.95,"estimate":None,"lower":None,"upper":None}


def canonical_oracle_info(card):
    faces=[{"name":face.get("name"),"oracle_text":face.get("oracle_text")} for face in (card.get("card_faces") or []) if isinstance(face,dict) and face.get("oracle_text")]
    parent=card.get("oracle_text") or None
    if parent and faces: status="PARENT_AND_FACE_TEXT_AVAILABLE"
    elif parent: status="PARENT_TEXT_AVAILABLE"
    elif faces: status="FACE_TEXT_AVAILABLE"
    else: status="MISSING"
    return {"status":status,"parent_text":parent,"faces":faces}


def source_text_status_by_engine(evidence):
    result={}
    for source in ("forge","xmage"):
        item=evidence.get(source,{})
        result[source]="NOT_AVAILABLE" if not item.get("present") else ("PRESENT" if str(item.get("source_oracle_text") or "").strip() else "MISSING")
    return result


def build_oracle_availability(probability_samples):
    source_sample_counts=Counter(); by_engine={s:Counter() for s in ("forge","xmage")}
    canonical_counts=Counter(); by_pattern=defaultdict(lambda:{"sample_count":0,"source_text_present":0,"source_text_missing":0,"canonical_parent_text_available":0,"canonical_face_text_available":0,"canonical_text_missing":0})
    missing_source_with_face=0
    for sample in probability_samples:
        source_sample_counts[sample["source_oracle_text_status"]]+=1
        for engine,status in sample["source_oracle_text_status_by_engine"].items(): by_engine[engine][status]+=1
        canonical=sample["canonical_oracle_text_status"]; canonical_counts[canonical]+=1
        row=by_pattern[sample["pattern_id"]];row["sample_count"]+=1
        row["source_text_present"]+=sample["source_oracle_text_status"]=="PRESENT"
        row["source_text_missing"]+=sample["source_oracle_text_status"]=="MISSING"
        row["canonical_parent_text_available"]+=canonical in {"PARENT_TEXT_AVAILABLE","PARENT_AND_FACE_TEXT_AVAILABLE"}
        row["canonical_face_text_available"]+=canonical in {"FACE_TEXT_AVAILABLE","PARENT_AND_FACE_TEXT_AVAILABLE"}
        row["canonical_text_missing"]+=canonical=="MISSING"
        missing_source_with_face+=sample["source_oracle_text_status"]=="MISSING" and canonical in {"FACE_TEXT_AVAILABLE","PARENT_AND_FACE_TEXT_AVAILABLE"}
    return {"unit":"primary probability sample review items (forced audit items excluded)","primary_sample_count":len(probability_samples),"source_oracle_text_status":{"PRESENT":source_sample_counts["PRESENT"],"MISSING":source_sample_counts["MISSING"]},"source_oracle_text_by_engine":{engine:{"PRESENT":counts["PRESENT"],"MISSING":counts["MISSING"],"NOT_AVAILABLE":counts["NOT_AVAILABLE"]} for engine,counts in by_engine.items()},"canonical_oracle_text_status":{status:canonical_counts[status] for status in ("PARENT_TEXT_AVAILABLE","FACE_TEXT_AVAILABLE","PARENT_AND_FACE_TEXT_AVAILABLE","MISSING")},"canonical_parent_text_available":canonical_counts["PARENT_TEXT_AVAILABLE"]+canonical_counts["PARENT_AND_FACE_TEXT_AVAILABLE"],"canonical_face_text_available":canonical_counts["FACE_TEXT_AVAILABLE"]+canonical_counts["PARENT_AND_FACE_TEXT_AVAILABLE"],"canonical_text_missing":canonical_counts["MISSING"],"source_missing_but_canonical_face_available":missing_source_with_face,"by_pattern":{pattern:values for pattern,values in sorted(by_pattern.items())}}


def deterministic_sample_id(pattern_id, oracle_id, source_record_identity):
    key="\x1f".join((pattern_id,str(oracle_id),str(source_record_identity)))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def sample_id_set_sha256(samples):
    ids=sorted(sample["sample_id"] if isinstance(sample,dict) else str(sample) for sample in samples)
    return hashlib.sha256(("\n".join(ids)+"\n").encode("utf-8")).hexdigest()


def sample_id_set_sha256(samples):
    ids=sorted(sample["sample_id"] if isinstance(sample,dict) else str(sample) for sample in samples)
    return hashlib.sha256(("\n".join(ids)+"\n").encode("utf-8")).hexdigest()


def forced_audit_sample_id(audit_id, pattern_id, source_record_identity):
    key="\x1f".join(("FORCED_FLAGGED_JOIN_AUDIT",audit_id,pattern_id,str(source_record_identity)))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def source_occurrence_parts(source_record_identity):
    return {part for part in str(source_record_identity).split("|") if part}


def can_reserve_sample_occurrences(source_record_identity, used_occurrences):
    return not (source_occurrence_parts(source_record_identity)&set(used_occurrences))


def stratified_stable_sample(candidates, sample_size):
    groups=defaultdict(list)
    for item in candidates: groups[tuple(item["stratum"][k] for k in sorted(item["stratum"]))].append(item)
    queues={key:sorted(values,key=lambda item:item["sample_id"]) for key,values in sorted(groups.items())}
    selected=[]
    while len(selected)<min(sample_size,len(candidates)):
        progressed=False
        for key in sorted(queues):
            if queues[key] and len(selected)<sample_size:
                selected.append(queues[key].pop(0));progressed=True
        if not progressed: break
    return selected


def stable_second_review_ids(samples, risk, fraction):
    if risk=="HIGH": return {s["sample_id"] for s in samples}
    if risk!="MEDIUM" or fraction<=0: return set()
    required=math.ceil(len(samples)*fraction)
    return {s["sample_id"] for s in sorted(samples,key=lambda s:hashlib.sha256((s["sample_id"]+"|reviewer-b").encode()).hexdigest())[:required]}


def java_review_excerpt(source, constructs, limit=5000):
    text=source.replace("\\n","\n")
    lines=text.splitlines(); terms=set(constructs)
    selected=set()
    for i,line in enumerate(lines):
        if any(term and term in line for term in terms):
            selected.update(range(max(0,i-2),min(len(lines),i+3)))
    excerpt="\n".join(lines[i] for i in sorted(selected))
    return excerpt[:limit]


def reviewable_record_identity(source, revision, row_index):
    return f"{source}@{revision}:row:{row_index:08d}"


def sample_stratum(card, forge_present, xmage_present):
    type_line=card.get("type_line") or ""
    card_type=type_line.split("—",1)[0].split("//",1)[0].strip() or "unknown"
    layout=card.get("layout") or "normal"
    faces=card.get("card_faces") or []
    face_kind="MULTIFACE" if len(faces)>1 or layout not in {"normal","token"} else "SINGLE_FACE"
    text=card.get("oracle_text") or ""
    text_length="SHORT" if len(text)<=120 else ("MEDIUM" if len(text)<=300 else "LONG")
    engine_mode="BOTH" if forge_present and xmage_present else ("FORGE_ONLY" if forge_present else "XMAGE_ONLY")
    return {"card_type":card_type,"face_kind":face_kind,"oracle_text_length":text_length,"available_engine_evidence":engine_mode}


def forge_parameter_inventory(record):
    text=str(record.get("output","")).replace("\\n","\n")
    result=defaultdict(list)
    for key,value in re.findall(r"\b([A-Za-z][\w]*)\$\s*([^|\r\n]+)",text):
        value=value.strip()
        if value and value not in result[key]: result[key].append(value[:500])
    return dict(sorted(result.items()))


def load_validation_plan(mapping_sha, source_revisions):
    import yaml
    plan=yaml.safe_load((ROOT/"validation_plan.yaml").read_text(encoding="utf-8"))
    scope=plan["validation_scope"]
    expected={"extractor_version":VALIDATION_EXTRACTOR_VERSION,"mapping_sha256":mapping_sha,"source_set":source_revisions}
    actual={"extractor_version":scope.get("extractor_version"),"mapping_sha256":scope.get("mapping_sha256"),"source_set":scope.get("source_set")}
    if actual!=expected: raise RuntimeError(f"Validation plan scope does not match pinned run: plan={actual}, run={expected}")
    return plan


def generate_review_artifacts(sf, f_matches, x_matches, forge_extracts, xmage_extracts, forge_map, xmage_map, source_revisions, reviewed_decisions):
    mapping_sha=hashlib.sha256((ROOT/"mappings.yaml").read_bytes()).hexdigest()
    plan=load_validation_plan(mapping_sha,source_revisions)
    samples=[]; inventories=[]; used_occurrences=set()
    matched_ids=set(f_matches)|set(x_matches)
    both_engine_ids=set(f_matches)&set(x_matches)
    known_join_warning_ids={d["oracle_id"] for d in reviewed_decisions.values() if d["action"]=="KEEP_WITH_FLAG"}
    pattern_candidate_lookup={}

    def matches_for_construct(source, index, construct):
        if source=="forge":
            return [item for item in f_matches.get(index,[]) if construct in item[2]]
        return [item for item in x_matches.get(index,[]) if construct in item[4]]

    def row_id(source,item):
        revision=source_revisions[source]
        return reviewable_record_identity(source,revision,item[-1])

    def evidence_payload(source,index,chosen,selected_constructs,card):
        if source=="forge":
            record,method,actions,attrs,snips,relation,diag,rec_index=chosen
            selected_snippets=[snippet for snippet in snips if any(token in snippet for token in selected_constructs)] or snips
            return {"present":True,"source_record_identity":row_id(source,chosen),"match_method":method,"selected_constructs":sorted(selected_constructs),"actions":sorted(set(actions)),"source_oracle_text":oracle_text(record),"oracle_text_comparison":relation,"parameters":forge_parameter_inventory(record),"snippet":"\n".join(selected_snippets[:8])[:5000],"join_review":join_review_metadata(source,card.get("oracle_id"),reviewed_decisions)}
        record,method,imports,classes,semantic,snippet,relation,diag,rec_index=chosen
        java=record.get("completion",record.get("output",""))
        excerpt=java_review_excerpt(java,set(selected_constructs)|set(semantic))
        return {"present":True,"source_record_identity":row_id(source,chosen),"match_method":method,"selected_constructs":sorted(selected_constructs),"semantic_classes":semantic,"imports":imports,"source_oracle_text":oracle_text(record),"oracle_text_comparison":relation,"prompt":record.get("prompt",""),"java_excerpt":excerpt,"join_review":join_review_metadata(source,card.get("oracle_id"),reviewed_decisions)}

    def build_review_item(spec,candidate,sample_id,selection_basis,second_review_required=False,known_join_warning=False,forced_decision=None):
        index=candidate["index"];card=candidate["card"];chosen=candidate["chosen"]
        construct_specs=spec.get("external_constructs") or [{"source":spec["source"],"token":spec["external_construct"]}]
        pattern_constructs=defaultdict(set)
        for construct in construct_specs: pattern_constructs[construct["source"]].add(construct.get("token") or construct.get("class"))
        forge_choice=chosen.get("forge",{});xmage_choice=chosen.get("xmage",{})
        if not forge_choice and f_matches.get(index): forge_choice={"_corroborating":min(f_matches[index],key=lambda value:value[-1])}
        if not xmage_choice and x_matches.get(index): xmage_choice={"_corroborating":min(x_matches[index],key=lambda value:value[-1])}
        forge_items=list(forge_choice.values());xmage_items=list(xmage_choice.values())
        forge_payload=evidence_payload("forge",index,forge_items[0],pattern_constructs.get("forge",set()),card) if forge_items else {"present":False}
        xmage_payload=evidence_payload("xmage",index,xmage_items[0],pattern_constructs.get("xmage",set()),card) if xmage_items else {"present":False}
        all_review=[]
        for source,items in (("forge",forge_items),("xmage",xmage_items)):
            for _ in items:
                meta=join_review_metadata(source,card.get("oracle_id"),reviewed_decisions)
                if meta: all_review.append({"source":source,**meta})
        canonical=canonical_oracle_info(card)
        evidence={"forge":forge_payload,"xmage":xmage_payload}
        source_statuses=source_text_status_by_engine(evidence)
        required_sources=("forge","xmage") if spec["source"]=="cross" else (spec["source"],)
        row={"sample_id":sample_id,"validation_status":"AWAITING_REVIEW","pattern_id":spec["pattern_id"],"pattern_version":spec["pattern_version"],"validation_scope":{"extractor_version":VALIDATION_EXTRACTOR_VERSION,"mapping_sha256":mapping_sha,"source_set":source_revisions},"pattern":{"kind":spec.get("pattern_kind","SOURCE_MAPPING"),"source":spec["source"],"external_construct":spec.get("external_construct"),"external_constructs":construct_specs if spec["source"]=="cross" else None,"proposed_requirement":spec["proposed_requirement"],"risk":spec["risk"],"context_fields_to_check":spec.get("context_fields",[])},"source_record_identity":candidate["identity"],"card":{"oracle_id":card.get("oracle_id"),"name":card.get("name"),"type_line":card.get("type_line"),"layout":card.get("layout"),"mana_cost":card.get("mana_cost"),"oracle_text":card.get("oracle_text"),"faces":[{"name":f.get("name"),"oracle_text":f.get("oracle_text")} for f in (card.get("card_faces") or []) if isinstance(f,dict)]},"evidence":evidence,"source_oracle_text_status_by_engine":source_statuses,"source_oracle_text_status":"PRESENT" if all(source_statuses.get(source)=="PRESENT" for source in required_sources) else "MISSING","source_oracle_text_missing_sources":[source for source in required_sources if source_statuses.get(source)!="PRESENT"],"canonical_oracle_text_status":canonical["status"],"canonical_oracle":{"parent_text":canonical["parent_text"],"faces":canonical["faces"]},"oracle_support_available":canonical["status"]!="MISSING","join_review":{"status":"KEEP_WITH_FLAG" if any(r["join_review_status"]=="KEEP_WITH_FLAG" for r in all_review) else ("REVIEWED_KEEP_JOIN" if all_review else "NOT_IN_SUSPICIOUS_JOIN_AUDIT"),"decisions":all_review},"stratum":candidate["stratum"],"selection_basis":selection_basis,"known_join_warning":known_join_warning,"covered_by_probability_sample":selection_basis=="PROBABILITY_SAMPLE" and known_join_warning,"review_protocol":{"reviewer_a_required":True,"second_review_required":second_review_required,"blind_second_review":second_review_required,"second_review_fraction":spec.get("second_review_fraction",0.0) if selection_basis=="PROBABILITY_SAMPLE" else 0.0},"review_fields":{"decision":None,"reason":None,"suggested_requirement":None}}
        if forced_decision:
            row["forced_join_audit"]={"audit_id":join_audit_id(forced_decision["source"],forced_decision["oracle_id"]),"source":forced_decision["source"],"oracle_id":forced_decision["oracle_id"],"card_name":forced_decision["card_name"],"join_review_status":forced_decision["action"],"join_review_reason":forced_decision["reason"]}
        return row

    for spec in plan["patterns"]:
        constructs=spec.get("external_constructs") or [{"source":spec["source"],"token":spec["external_construct"]}]
        population=[]; source_occurrence_counts=Counter()
        for idx,card in enumerate(sf):
            if idx not in matched_ids: continue
            chosen_by_source={}
            present=True
            for construct in constructs:
                source=construct["source"]
                token=construct.get("token") or construct.get("class")
                hits=matches_for_construct(source,idx,token)
                if not hits:
                    present=False;break
                chosen=min(hits,key=lambda item:item[-1])
                chosen_by_source.setdefault(source,{})[token]=chosen
            if not present: continue
            population.append((idx,card,chosen_by_source))
        if spec["source"]=="forge":
            token=spec["external_construct"]
            source_occurrence_counts["forge"]=sum(actions.count(token) for _,actions,_,_ in forge_extracts)
        elif spec["source"]=="xmage":
            token=spec["external_construct"]
            source_occurrence_counts["xmage"]=sum(token in semantic for _,_,_,semantic,_ in xmage_extracts)
        else:
            for construct in constructs:
                source=construct["source"]; token=construct.get("token") or construct.get("class")
                if source=="forge": source_occurrence_counts[source]=sum(actions.count(token) for _,actions,_,_ in forge_extracts)
                else: source_occurrence_counts[source]=sum(token in semantic for _,_,_,semantic,_ in xmage_extracts)

        candidates=[]
        for idx,card,chosen_by_source in population:
            identities=[]
            for source in sorted(chosen_by_source):
                for token,entry in sorted(chosen_by_source[source].items()): identities.append(row_id(source,entry))
            for source,matched in (("forge",f_matches.get(idx,[])),("xmage",x_matches.get(idx,[]))):
                if matched and source not in chosen_by_source:
                    identities.append(row_id(source,min(matched,key=lambda item:item[-1])))
            identity="|".join(identities)
            sid=deterministic_sample_id(spec["pattern_id"],card.get("oracle_id"),identity)
            stratum=sample_stratum(card,idx in f_matches,idx in x_matches)
            candidates.append({"sample_id":sid,"oracle_id":card.get("oracle_id"),"name":card.get("name"),"identity":identity,"stratum":stratum,"index":idx,"card":card,"chosen":chosen_by_source})
        pattern_candidate_lookup[spec["pattern_id"]]={c["oracle_id"]:c for c in candidates}
        # Sampling is per-card; reserve source rows already used by earlier patterns so an
        # occurrence is not duplicated across the review packet. Population remains unfiltered.
        available=[]
        for candidate in candidates:
            if can_reserve_sample_occurrences(candidate["identity"],used_occurrences): available.append(candidate)
        requested=min(spec["sample_size"],len(available))
        selected=stratified_stable_sample(available,requested)
        for candidate in selected: used_occurrences.update(source_occurrence_parts(candidate["identity"]))
        second_ids=stable_second_review_ids(selected,spec["risk"],spec.get("second_review_fraction",0.0))
        output_rows=[build_review_item(spec,candidate,candidate["sample_id"],"PROBABILITY_SAMPLE",candidate["sample_id"] in second_ids,candidate["oracle_id"] in known_join_warning_ids) for candidate in selected]
        samples.extend(output_rows)
        both_count=sum(idx in both_engine_ids for idx,_,_ in population)
        interval_plan=primary_interval_summary(len(population),len(selected),plan["sampling"].get("interval_method_threshold",0.05))
        inventories.append({"pattern_id":spec["pattern_id"],"pattern_version":spec["pattern_version"],"validation_scope":plan["validation_scope"],"source":spec["source"],"external_construct":spec.get("external_construct"),"external_constructs":constructs if spec["source"]=="cross" else None,"proposed_requirement":spec["proposed_requirement"],"risk":spec["risk"],"rationale":spec["rationale"],"context_fields_to_check":spec.get("context_fields",[]),"population_size":len(population),"source_population_records":dict(source_occurrence_counts),"cards_with_both_engine_evidence":both_count,"target_sample_size":spec["sample_size"],"sample_size":len(selected),"probability_sample_size":len(selected),"forced_audit_sample_size":0,"sampling_fraction":interval_plan["sampling_fraction"],"planned_interval_method":interval_plan["planned_interval_method"],"planned_interval":interval_plan["interval"],"sample_ids":[r["sample_id"] for r in output_rows],"probability_sample_ids":[r["sample_id"] for r in output_rows],"forced_sample_ids":[],"second_review_fraction":spec.get("second_review_fraction",0.0),"second_review_required_samples":len(second_ids),"validation_status":"AWAITING_REVIEW","precision":interval_plan["interval"],"inter_rater_agreement":"NOT_AVAILABLE"})
    probability_samples=list(samples)
    low_probability_samples=[s for s in probability_samples if s["pattern"]["risk"]=="LOW"]
    if len(probability_samples)!=460 or sample_id_set_sha256(probability_samples)!=PHASE_0_2A_SAMPLE_IDS_SHA256:
        raise RuntimeError("Phase 0.2A probability sample IDs changed; refusing to invalidate existing reviews")
    if len(low_probability_samples)!=60 or sample_id_set_sha256(low_probability_samples)!=PHASE_0_2A_LOW_SAMPLE_IDS_SHA256:
        raise RuntimeError("Phase 0.2A LOW-risk sample IDs changed; refusing to invalidate existing reviews")
    probability_ids_by_card=defaultdict(list)
    for sample in probability_samples: probability_ids_by_card[sample["card"]["oracle_id"]].append(sample["sample_id"])

    forced_samples=[]; forced_by_pattern=Counter(); forced_ids_by_pattern=defaultdict(list); warning_coverage=[]
    specs_by_id={spec["pattern_id"]:spec for spec in plan["patterns"]}
    for decision in reviewed_decisions.values():
        if decision["action"]!="KEEP_WITH_FLAG": continue
        oid=decision["oracle_id"]
        relevant=[spec for spec in plan["patterns"] if oid in pattern_candidate_lookup[spec["pattern_id"]]]
        covered=bool(probability_ids_by_card.get(oid))
        forced_id=None
        if relevant and not covered:
            spec=relevant[0]
            candidate=pattern_candidate_lookup[spec["pattern_id"]][oid]
            audit_id=join_audit_id(decision["source"],oid)
            forced_id=hashlib.sha256("\x1f".join(("FORCED_FLAGGED_JOIN_AUDIT",audit_id,spec["pattern_id"],candidate["identity"])).encode("utf-8")).hexdigest()[:24]
            forced=build_review_item(spec,candidate,forced_id,"FORCED_FLAGGED_JOIN_AUDIT",False,True,decision)
            forced["forced_join_audit"]["relevant_pattern_ids"]=[p["pattern_id"] for p in relevant]
            forced["forced_join_audit"]["covered_by_probability_sample"]=False
            forced["review_protocol"]["second_review_required"]=False
            forced["review_protocol"]["blind_second_review"]=False
            forced_samples.append(forced);forced_by_pattern[spec["pattern_id"]]+=1;forced_ids_by_pattern[spec["pattern_id"]].append(forced_id)
        warning_coverage.append({"source":decision["source"],"oracle_id":oid,"card_name":decision["card_name"],"join_review_status":decision["action"],"join_review_reason":decision["reason"],"relevant_pattern_ids":[p["pattern_id"] for p in relevant],"covered_by_probability_sample":covered,"forced_sample_id":forced_id,"coverage_status":"COVERED_BY_PROBABILITY_SAMPLE" if covered else ("COVERED_BY_FORCED_AUDIT" if forced_id else "NOT_RELEVANT_TO_SELECTED_PATTERNS"),"review_sample_ids":sorted(probability_ids_by_card.get(oid,[])+([forced_id] if forced_id else []))})
    relevant_warnings=[w for w in warning_coverage if w["relevant_pattern_ids"]]
    if any(w["coverage_status"]=="NOT_RELEVANT_TO_SELECTED_PATTERNS" for w in relevant_warnings): raise RuntimeError("A flagged join relevant to a selected pattern has no review coverage")

    probability_count=len(probability_samples); forced_count=len(forced_samples); all_samples=probability_samples+forced_samples
    if probability_count!=sum(p["sample_size"] for p in inventories): raise RuntimeError("Pattern probability sample totals do not match the Phase 0.2A baseline")
    if probability_count+forced_count>500: raise RuntimeError(f"Review packet cap exceeded: {probability_count+forced_count}")
    for inv in inventories:
        inv["probability_sample_size"]=inv["sample_size"]
        inv["forced_audit_sample_size"]=forced_by_pattern[inv["pattern_id"]]
        inv["forced_sample_ids"]=sorted(forced_ids_by_pattern[inv["pattern_id"]])
        interval_plan=primary_interval_summary(inv["population_size"],inv["probability_sample_size"],plan["sampling"].get("interval_method_threshold",0.05))
        inv["sampling_fraction"]=interval_plan["sampling_fraction"]
        inv["planned_interval_method"]=interval_plan["planned_interval_method"]
        inv["planned_interval"]=interval_plan["interval"]
        inv["precision"]=interval_plan["interval"]
        inv["probability_sample_ids"]=list(inv["sample_ids"])
    all_sample_occurrences=[part for row in all_samples for part in source_occurrence_parts(row["source_record_identity"])]
    if len(all_sample_occurrences)!=len(set(all_sample_occurrences)): raise RuntimeError("A source record occurrence was included more than once in the review packet")
    write_jsonl(OUT/"review_samples.jsonl",all_samples)
    write_jsonl(OUT/"forced_audit_samples.jsonl",forced_samples)

    availability=build_oracle_availability(probability_samples)
    probability_missing=sum(sample["source_oracle_text_status"]=="MISSING" for sample in probability_samples)
    finite_count=sum(p["planned_interval_method"]=="FINITE_POPULATION_HYPERGEOMETRIC" for p in inventories)
    warning_naturally_sampled=sum(w["covered_by_probability_sample"] for w in warning_coverage)
    warning_forced=sum(w["forced_sample_id"] is not None for w in warning_coverage)
    inventory={"validation_scope":plan["validation_scope"],"plan_id":plan["plan_id"],"review_batch_id":plan["review_batch_id"],"sampling":plan["sampling"],"pattern_count":len(inventories),"total_population_occurrences":sum(sum(p["source_population_records"].values()) for p in inventories),"total_samples":probability_count,"probability_sample_count":probability_count,"forced_audit_sample_count":forced_count,"total_review_packet_items":len(all_samples),"phase_0_2a_sample_ids_preserved":True,"phase_0_2a_sample_ids_sha256":PHASE_0_2A_SAMPLE_IDS_SHA256,"phase_0_2a_low_sample_ids_sha256":PHASE_0_2A_LOW_SAMPLE_IDS_SHA256,"low_risk_patterns":sum(p["risk"]=="LOW" for p in inventories),"medium_risk_patterns":sum(p["risk"]=="MEDIUM" for p in inventories),"high_risk_patterns":sum(p["risk"]=="HIGH" for p in inventories),"second_review_required_samples":sum(p["second_review_required_samples"] for p in inventories),"validation_status":validation_status_from_results([]),"patterns_validated":0,"precision_available":False,"inter_rater_agreement_available":False,"interval_method_counts":{"WILSON_BINOMIAL":len(inventories)-finite_count,"FINITE_POPULATION_HYPERGEOMETRIC":finite_count},"probability_samples_with_source_text_missing":probability_missing,"oracle_text_availability":availability,"join_quality_warnings":warning_coverage,"known_join_warning_count":len(warning_coverage),"relevant_warning_count":sum(bool(w["relevant_pattern_ids"]) for w in warning_coverage),"naturally_sampled_warning_count":warning_naturally_sampled,"forced_warning_count":warning_forced,"patterns":inventories}
    write_json(OUT/"pattern_inventory.json",inventory)
    return inventory


def load_join_decisions():
    import yaml
    path=ROOT/"reviewed_join_decisions.yaml"
    raw=yaml.safe_load(path.read_text(encoding="utf-8")) or []
    result={}
    allowed_results={"VALID_JOIN_STALE_WORDING","VALID_JOIN_FORMATTING_VARIANT","VALID_JOIN_MULTIFACE_VARIANT","VALID_JOIN_TEMPLATE_VARIANT","VALID_JOIN_OTHER","SOURCE_RECORD_WRONG_OR_CORRUPT","SOURCE_RECORD_NONSTANDARD_OR_CUSTOM","SOURCE_RECORD_INCOMPLETE","BAD_JOIN_NAME_COLLISION","BAD_JOIN_FACE_COLLISION","BAD_JOIN_OTHER","UNRESOLVED"}
    allowed_actions={"KEEP_JOIN","KEEP_WITH_FLAG","REJECT_JOIN"}
    for decision in raw:
        aid=decision["audit_id"]
        if aid in result: raise ValueError(f"Duplicate reviewed join decision: {aid}")
        if decision.get("result") not in allowed_results or decision.get("action") not in allowed_actions or not decision.get("reason"):
            raise ValueError(f"Invalid reviewed join decision: {aid}")
        result[aid]=decision
    return result


def jsonable(value):
    if isinstance(value, dict): return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [jsonable(v) for v in value]
    if hasattr(value, "item"):
        try: return value.item()
        except Exception: pass
    return value


def flatten_text(value):
    if isinstance(value, dict):
        for v in value.values(): yield from flatten_text(v)
    elif isinstance(value, (list, tuple)):
        for v in value: yield from flatten_text(v)
    elif isinstance(value, str): yield value


def fields(record):
    result = {}
    for k, v in record.items():
        if v is None: continue
        if isinstance(v, str): result[k] = v[:400]
        elif isinstance(v, (dict, list, tuple)):
            sample = v[:2] if isinstance(v, (list, tuple)) else dict(list(v.items())[:4])
            result[k] = {"type": type(v).__name__, "items": len(v), "sample": jsonable(sample)}
        else: result[k] = jsonable(v)
    return result


def text_for(record, keys):
    vals = []
    for key, val in record.items():
        if any(part in key.casefold() for part in keys): vals.extend(flatten_text(val))
    return "\n".join(vals)


def card_name(record):
    for key in record:
        if key.casefold() in {"name", "card_name", "cardname"}:
            val = record[key]
            if isinstance(val, str): return val
            if isinstance(val, dict):
                for sub in val.values():
                    if isinstance(sub, str): return sub
    # Some corpora wrap source JSON in prompt/input fields.
    for value in flatten_text(record):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict) and isinstance(parsed.get("name"), str): return parsed["name"]
        except Exception: pass
    for key in ("prompt", "input", "text"):
        value = record.get(key)
        if isinstance(value, str):
            m = re.search(r"(?im)^\s*Name:\s*(.+?)\s*$", value)
            if m: return m.group(1).strip()
    return ""


def oracle_text(record):
    direct = text_for(record, ("oracle_text", "oracletext", "rules_text", "card_text"))
    if direct: return direct
    for key in ("input", "prompt"):
        value = record.get(key)
        if not isinstance(value, str): continue
        try:
            obj=json.loads(value)
            if isinstance(obj,dict) and isinstance(obj.get("oracle_text"),str): return obj["oracle_text"]
        except Exception: pass
        parts=re.findall(r"^\s*Oracle Text:\s*(.*?)(?=^\s*(?:Name|Mana Cost|CMC|Cmc|Type Line|Colors|Color Identity|Keywords|Rarity|Power|Toughness|Loyalty|Defense|Oracle Text):|\Z)",value,re.I|re.M|re.S)
        parts=[part.strip() for part in parts if part.strip()]
        if parts: return "\n".join(parts)
    return ""


def oracle_text_relation(source_record, scryfall_card):
    source=norm(oracle_text(source_record))
    if not source: return "MISSING"
    canonical=[scryfall_card.get("oracle_text") or ""]
    canonical.extend(face.get("oracle_text","") for face in (scryfall_card.get("card_faces") or []) if isinstance(face,dict))
    return "MATCH" if source in {norm(t) for t in canonical if t} else "MISMATCH"


def scryfall_text_options(card):
    faces=[f.get("oracle_text","") for f in (card.get("card_faces") or []) if isinstance(f,dict) and f.get("oracle_text")]
    values=[card.get("oracle_text") or "",*faces]
    if len(faces)>1: values.append("\n".join(faces))
    return [norm(t) for t in values if t]


def xmage_semantic_classes(classes):
    """Exclude targeting/filter scaffolding and generic framework base classes."""
    return sorted(c for c in set(classes) if c not in GENERIC_XMAGE_CLASSES and class_category(c) in {"Ability", "Effect", "Cost", "Condition", "ReplacementEffect"})


def resolution_bucket(has_external, mapped_count, unmapped_count, completeness_proven=False):
    if not has_external: return "NO_EXTERNAL_EVIDENCE"
    if not mapped_count: return "FULLY_UNRESOLVED"
    if unmapped_count: return "PARTIALLY_RESOLVED"
    if completeness_proven: return "FULLY_RESOLVED"
    return "COMPLETENESS_UNVERIFIED"


def partition_tokens(source, tokens, mapping, match_method=None, record_index=None):
    mapped=defaultdict(list); unmapped=[]
    for token in tokens:
        item={"source":source,"token":token}
        if match_method is not None: item["match_method"]=match_method
        if record_index is not None: item["source_record_index"]=record_index
        if token in mapping: mapped[mapping[token]].append(item)
        else: unmapped.append(item)
    return mapped,unmapped


def summarize_card_resolution(scryfall_total, forge_ids, xmage_ids, mapped_by_card, unmapped_by_card):
    external=set(forge_ids)|set(xmage_ids); mapped=set(mapped_by_card); unmapped=set(unmapped_by_card)
    buckets=Counter(resolution_bucket(True,1 if i in mapped else 0,1 if i in unmapped else 0,False) for i in external)
    return {"scryfall_total":scryfall_total,"with_any_external_evidence":len(external),"with_forge_evidence":len(forge_ids),"with_xmage_evidence":len(xmage_ids),"with_both_evidence":len(set(forge_ids)&set(xmage_ids)),"with_any_mapped_requirement":len(mapped),"fully_unresolved":buckets["FULLY_UNRESOLVED"],"partially_resolved":buckets["PARTIALLY_RESOLVED"],"fully_resolved":buckets["FULLY_RESOLVED"],"resolution_completeness_unverified":buckets["COMPLETENESS_UNVERIFIED"]}


def template_normalize(value, name, type_line=""):
    text=unicodedata.normalize("NFKC",str(value or "")).casefold()
    if name:
        text=re.sub(rf"(?<!\w){re.escape(name.casefold())}(?!\w)"," <self> ",text)
    self_terms={"this creature","this artifact","this enchantment","this planeswalker","this land","this permanent","this spell","this card","this vehicle"}
    first=(type_line or "").split("—",1)[0].split("//",1)[0].casefold()
    for term in self_terms:
        text=re.sub(rf"(?<!\w){re.escape(term)}(?!\w)"," <self> ",text)
    return norm(text)


def mismatch_diagnostic(source, source_record, card):
    """Return deterministic diagnostic category, text similarity and join status."""
    source_text=oracle_text(source_record)
    current=scryfall_text(card)
    name=card.get("name") or card_name(source_record)
    faces=[f.get("oracle_text","") for f in (card.get("card_faces") or []) if isinstance(f,dict) and f.get("oracle_text")]
    if not norm(source_text): return {"category":"UNCLASSIFIED","join_status":"JOIN_TEXT_MISSING","similarity":None,"notes":"Source Oracle text was not extracted."}
    # This function is used for mismatches only; direct normalized equality is a defensive check.
    if norm(source_text)==norm(current) or any(norm(source_text)==norm(t) for t in faces):
        return {"category":"EXACT_AFTER_FACE_TEXT_COMPARISON" if faces else "EXACT_AFTER_REMINDER_TEXT_REMOVAL","join_status":"JOIN_TEXT_MATCH","similarity":1.0,"notes":"Exact normalized text comparison."}
    source_no_reminder=re.sub(r"\([^()]*\)"," ",source_text)
    current_no_reminder=re.sub(r"\([^()]*\)"," ",current)
    if norm(source_no_reminder)==norm(current_no_reminder):
        category="EXACT_AFTER_REMINDER_TEXT_REMOVAL"
        return {"category":category,"join_status":"JOIN_TEXT_VARIANT","similarity":1.0,"notes":"Texts agree after removing parenthetical text for diagnosis only."}
    if template_normalize(source_text,name,card.get("type_line"))==template_normalize(current,name,card.get("type_line")):
        return {"category":"EXACT_AFTER_CARDNAME_TEMPLATE_NORMALIZATION","join_status":"JOIN_TEXT_VARIANT","similarity":1.0,"notes":"Self-name and self-reference templates agree after normalization."}
    if faces:
        joined="\n".join(faces)
        if norm(source_text)==norm(joined):
            return {"category":"EXACT_AFTER_FACE_TEXT_COMPARISON","join_status":"JOIN_TEXT_VARIANT","similarity":1.0,"notes":"Source text equals the combined face text representation."}
    similarity=difflib.SequenceMatcher(None,norm(source_text),norm(current)).ratio()
    source_tokens=Counter(re.findall(r"\w+",norm(source_text)))
    current_tokens=Counter(re.findall(r"\w+",norm(current)))
    token_intersection=sum((source_tokens & current_tokens).values())
    token_union=sum((source_tokens | current_tokens).values()) or 1
    overlap=token_intersection/token_union
    if source=="xmage" and any(marker in source_text for marker in ("Oracle Text:","Color Identity:","\nColors:","\nRarity:")):
        category="LIKELY_PROMPT_EXTRACTION_ARTIFACT"
        notes="Extracted Oracle text appears to include prompt labels or metadata."
    elif faces and max([difflib.SequenceMatcher(None,norm(source_text),norm(t)).ratio() for t in faces]+[0])>=0.55:
        category="MULTIFACE_REPRESENTATION_DIFFERENCE"
        notes="Text overlaps a face representation but does not exactly match a single face."
    elif Counter(re.findall(r"\w+",norm(source_text)))==Counter(re.findall(r"\w+",norm(current))):
        category="LIKELY_FORMATTING_DIFFERENCE"
        notes="Word multiset is equal but normalized sequence differs."
    elif similarity>=0.55 or overlap>=0.40:
        category="LIKELY_STALE_ORACLE_WORDING"
        notes="Substantial lexical overlap suggests wording or version drift; this is diagnostic only."
    elif similarity<0.20 and overlap<0.20:
        category="POSSIBLE_BAD_JOIN"
        notes="Very low lexical overlap under an exact-name join; manual identity review is recommended."
    else:
        category="UNCLASSIFIED"
        notes="No deterministic diagnostic rule was decisive."
    join="JOIN_TEXT_MISMATCH_REVIEW" if category in {"POSSIBLE_BAD_JOIN","UNCLASSIFIED","LIKELY_PROMPT_EXTRACTION_ARTIFACT"} else "JOIN_TEXT_VARIANT"
    return {"category":category,"join_status":join,"similarity":round(similarity,4),"token_overlap":round(overlap,4),"notes":notes}


def mismatch_sample(source, record, card, method, diagnostic, record_index=None):
    return {"source":source,"card_name":card.get("name"),"oracle_id":card.get("oracle_id"),"match_method":method,
            "current_scryfall_text":scryfall_text(card),"source_text":oracle_text(record),
            "category":diagnostic["category"],"join_status":diagnostic["join_status"],"similarity":diagnostic.get("similarity"),
            "token_overlap":diagnostic.get("token_overlap"),"notes":diagnostic["notes"],"source_record_index":record_index,
            "audit_id":join_audit_id(source,card.get("oracle_id"))}


def source_join_context(source, record):
    if source=="forge":
        try: obj=json.loads(record.get("input", "{}"))
        except Exception: obj={}
        return {k:obj.get(k) for k in ("name","type_line","mana_cost","oracle_text") if obj.get(k) is not None}
    prompt=record.get("prompt","")
    result={}
    for field in ("Layout","Name","Mana Cost","Cmc","Type Line","Colors","Color Identity","Keywords","Produced Mana","Rarity"):
        m=re.search(rf"(?im)^\s*{re.escape(field)}:\s*(.*?)\s*$",prompt)
        if m: result[field.casefold().replace(" ","_")]=m.group(1)
    return result


def build_join_audit_record(sample, source_record, card, decision, name_match_count):
    context=source_join_context(sample["source"],source_record)
    face_names=[f.get("name") for f in (card.get("card_faces") or []) if isinstance(f,dict) and f.get("name")]
    source_name=context.get("name") or context.get("prompt_name") or sample["card_name"]
    type_value=context.get("type_line")
    sf_type=card.get("type_line") or ""
    mojibake_dash="".join(chr(i) for i in (0xe2,0x20ac,0x201d))
    raw_type=context.get("type_line") or ""
    type_encoding_artifact=mojibake_dash in raw_type
    normalize_type=lambda value: norm(str(value or "").replace(mojibake_dash,"—").replace("\ufffd","—"))
    mana=context.get("mana_cost")
    sf_mana=card.get("mana_cost")
    alias=bool(face_names and norm(source_name) in {norm(n) for n in face_names})
    return {
        "audit_id":sample["audit_id"],"source":sample["source"],"oracle_id":sample["oracle_id"],"card_name":sample["card_name"],"match_method":sample["match_method"],
        "source_text":sample["source_text"],"scryfall_text":sample["current_scryfall_text"],"source_type_or_context":context,
        "scryfall_type_line":sf_type,"layout":card.get("layout"),
        "diagnostics":{"normalized_similarity":sample.get("similarity"),"token_overlap":sample.get("token_overlap"),"face_names":face_names,"possible_alias_or_face_match":alias,"normalized_name_candidate_count":name_match_count,"type_line_match":normalize_type(type_value)==normalize_type(sf_type) if type_value else None,"type_line_encoding_artifact":type_encoding_artifact,"mana_cost_match":norm(mana)==norm(sf_mana) if mana is not None else None},
        "audit_result":decision["result"],"reason":decision["reason"],"action":decision["action"],"source_record_index":sample.get("source_record_index"),
        "review_provenance":{"file":"reviewed_join_decisions.yaml","decision_applied":True},
    }


def scryfall_text(card):
    if card.get("oracle_text"): return card["oracle_text"]
    return "\n".join(f"{face.get('name','')}: {face.get('oracle_text','')}".strip(": ") for face in (card.get("card_faces") or []) if isinstance(face,dict) and face.get("oracle_text"))


def mapping_coverage(counts, mapping):
    total=sum(counts.values()); covered=sum(count for token,count in counts.items() if token in mapping)
    unique=len(counts); mapped_unique=sum(token in mapping for token in counts)
    return {"unique_tokens":unique,"mapped_unique_tokens":mapped_unique,"unmapped_unique_tokens":unique-mapped_unique,
            "mapped_tokens":sorted(token for token in counts if token in mapping),"unmapped_tokens":sorted(token for token in counts if token not in mapping),
            "occurrences_total":total,"occurrences_mapped":covered,"occurrences_unmapped":total-covered,
            "occurrence_coverage":covered/total if total else 0.0,"occurrence_coverage_percent":100*covered/total if total else 0.0,
            "unique_token_coverage_percent":100*mapped_unique/unique if unique else 0.0}


def unmapped_vocab_rows(counts, extracts, source):
    examples=defaultdict(set)
    for item in extracts:
        if source=="forge":
            record,tokens=item[0],item[1]
        else:
            record,tokens=item[0],item[3]
        name=card_name(record)
        if name:
            for token in set(tokens): examples[token].add(name)
    return [(token,count,"; ".join(sorted(examples[token],key=lambda n:(norm(n),n))[:5])) for token,count in counts.most_common()]


def build_mismatch_audit(records, totals):
    result={"method":"deterministic text diagnostics; identity remains exact-only","sources":{}}
    for source in ("forge","xmage"):
        rows=sorted(records[source],key=lambda r:(r["category"],norm(r["card_name"] or ""),r["oracle_id"] or "",r["source_text"]))
        groups=defaultdict(list)
        for row in rows: groups[row["category"]].append(row)
        total=len(rows); classified=total-len(groups.get("UNCLASSIFIED",[]))
        exact_categories={"EXACT_AFTER_REMINDER_TEXT_REMOVAL","EXACT_AFTER_CARDNAME_TEMPLATE_NORMALIZATION","EXACT_AFTER_FACE_TEXT_COMPARISON"}
        exact_explained=sum(len(groups.get(category,[])) for category in exact_categories)
        categories={}
        for category,items in sorted(groups.items()):
            categories[category]={"count":len(items),"percentage_of_mismatches":100*len(items)/total if total else 0.0,"examples":items[:20]}
        review_count=sum(1 for row in rows if row["join_status"]=="JOIN_TEXT_MISMATCH_REVIEW")
        result["sources"][source]={"matched_text_mismatches":total,"mismatch_records_with_text":totals[source].get("MISMATCH",0),"suspicious_joins":review_count,
            "classified_count":classified,"classified_percentage":100*classified/total if total else 0.0,
            "exactly_explained_count":exact_explained,"exactly_explained_percentage":100*exact_explained/total if total else 0.0,
            "unclassified_count":len(groups.get("UNCLASSIFIED",[])),"categories":categories}
    return result


def all_strings(record): return "\n".join(flatten_text(record))


def forge_extract(source):
    text = source if isinstance(source, str) else "\n".join(flatten_text(source))
    text = text.replace("\\n", "\n")
    actions, attrs, snippets = [], [], []
    # Forge ability/effect forms: A:SP$ Action |Field$ value; also record generic $ fields.
    for m in re.finditer(r"(?:^|[\n\r|:])\s*(?:(?:A:)?(?:AB|SP|DB)\$|[TS]:Mode\$)\s*([^|\r\n]+)([^\r\n]*)", text):
        action = m.group(1).strip()
        if action and re.fullmatch(r"[\w.-]+", action): actions.append(action)
        line = m.group(0).strip()
        snippets.append(line[:600])
        attrs.extend(re.findall(r"\b([A-Za-z][\w]*)\$", line))
    # Generic constructs can be nested or formatted on separate lines.
    attrs.extend(re.findall(r"\b([A-Za-z][\w]*)\$", text))
    return actions, attrs, snippets[:20]


def java_extract(source):
    text = source if isinstance(source, str) else "\n".join(flatten_text(source))
    imports = re.findall(r"(?m)^\s*import\s+(?:static\s+)?([\w.*]+)\s*;", text)
    # Limit to implementation vocabulary. Card class names are deliberately excluded.
    candidates = set(re.findall(r"\bnew\s+([A-Z][A-Za-z0-9_]*)", text))
    candidates.update(path.rsplit(".", 1)[-1] for path in imports)
    classes = {name for name in candidates if class_category(name) != "class_or_other" and name not in {"Ability", "Effect", "Cost", "Target", "Filter", "Condition"}}
    lines = text.splitlines()
    relevant = [line for line in lines if re.search(r"\b(?:import\s+(?:mage\.(?:abilities|filter|target)|static\s+mage\.)|new\s+[A-Z]\w*(?:Effect|Ability|Cost|Target|Filter|Condition))", line)]
    return imports, sorted(classes), "\n".join(relevant[:25])[:1600]


def load_sources():
    os.environ.setdefault("HF_HOME", str(RAW / "hf-home"))
    from datasets import load_dataset
    loaded = {}
    for key, repo in SOURCES.items():
        loaded[key] = load_dataset(repo, revision=PINNED_REVISIONS[key], cache_dir=str(RAW / "hf"))
    return loaded


def split_rows(ds):
    return {name: list(split) for name, split in ds.items()} if hasattr(ds, "items") else {"train": list(ds)}


def dataset_rows(loaded):
    return {k: split_rows(v) for k, v in loaded.items()}


def inventory(rows, revisions):
    out = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "datasets": {}}
    for key, splits in rows.items():
        first = next((r for rr in splits.values() for r in rr), {})
        out["datasets"][key] = {
            "repository": SOURCES[key], "revision": revisions.get(key),
            "splits": {n: len(rr) for n, rr in splits.items()}, "rows": sum(map(len, splits.values())),
            "columns": list(first.keys()), "sample_fields": fields(first),
        }
    return out


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(obj), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records: f.write(json.dumps(jsonable(r), ensure_ascii=False) + "\n")


def _read_jsonl(path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip(): yield json.loads(line)


def read_mapping():
    import yaml
    return yaml.safe_load((ROOT / "mappings.yaml").read_text(encoding="utf-8"))


def mine(rows):
    sf = [r for split in rows["scryfall"].values() for r in split]
    forge = [r for split in rows["forge"].values() for r in split]
    xmage = [r for split in rows["xmage"].values() for r in split]
    by_id, by_name, by_nt = {}, defaultdict(list), defaultdict(list)
    for i, r in enumerate(sf):
        oid = r.get("oracle_id")
        if oid: by_id.setdefault(str(oid), []).append(i)
        n = norm(r.get("name"))
        if n: by_name[n].append(i)
        nt = norm(r.get("oracle_text"))
        if n and nt: by_nt[(n, nt)].append(i)
        for face in r.get("card_faces") or []:
            fn = norm(face.get("name")) if isinstance(face, dict) else ""
            if fn: by_name[fn].append(i)

    def match(record):
        id_match=exact_oracle_id_match(record,by_id)
        if id_match is not None: return id_match
        name = norm(card_name(record))
        if not name: return None, "unmatched"
        cand = list(dict.fromkeys(by_name.get(name, [])))
        unique=select_unambiguous(cand)
        if unique is not None: return unique, "normalized_name"
        if len(cand) > 1:
            txt = norm(oracle_text(record))
            if txt:
                exact = [i for i in cand if txt in scryfall_text_options(sf[i])]
                unique=select_unambiguous(exact)
                if unique is not None: return unique, "normalized_name_and_oracle_text"
            return None, "ambiguous_normalized_name"
        txt = norm(oracle_text(record))
        if txt:
            exact = [i for i in by_nt.get((name, txt), []) if txt in scryfall_text_options(sf[i])]
            if len(exact) == 1: return exact[0], "normalized_name_and_oracle_text"
            if len(exact) > 1: return None, "ambiguous_normalized_name_and_oracle_text"
        return None, "unmatched"

    mapping=read_mapping(); forge_map=mapping.get("forge",{}); xmage_map=mapping.get("xmage",{})
    reviewed_decisions=load_join_decisions()
    forge_counts=Counter(); xmage_counts=Counter(); xmage_all_counts=Counter()
    forge_extracts=[]; xmage_extracts=[]
    f_matches=defaultdict(list); x_matches=defaultdict(list)
    f_matches_before=defaultdict(list); x_matches_before=defaultdict(list)
    unmatched_f=[]; unmatched_x=[]; ambiguous=[]
    mismatch_records={"forge":[],"xmage":[]}; text_counts={"forge":Counter(),"xmage":Counter()}
    suspicious=Counter()
    join_audit_records=[]; applied_decisions={}

    for rec_index, rec in enumerate(forge):
        idx,method=match(rec); actions,attrs,snips=forge_extract(rec.get("output",all_strings(rec)))
        forge_counts.update(actions); forge_extracts.append((rec,actions,attrs,snips))
        if idx is not None:
            relation=oracle_text_relation(rec,sf[idx]); text_counts["forge"][relation]+=1
            diagnostic=mismatch_diagnostic("forge",rec,sf[idx]) if relation=="MISMATCH" else {"category":None,"join_status":"JOIN_TEXT_MATCH" if relation=="MATCH" else "JOIN_TEXT_MISSING","similarity":1.0 if relation=="MATCH" else None,"notes":"Exact normalized match." if relation=="MATCH" else "Source Oracle text missing."}
            decision=None
            if relation=="MISMATCH":
                sample=mismatch_sample("forge",rec,sf[idx],method,diagnostic,rec_index)
                mismatch_records["forge"].append(sample)
                if diagnostic["join_status"]=="JOIN_TEXT_MISMATCH_REVIEW":
                    decision=lookup_join_decision(reviewed_decisions,sample["audit_id"])
                    if not decision: raise RuntimeError(f"No reviewed decision for suspicious join {sample['audit_id']}")
                    applied_decisions[sample["audit_id"]]=decision
                    join_audit_records.append(build_join_audit_record(sample,rec,sf[idx],decision,len(dict.fromkeys(by_name.get(norm(card_name(rec)),[])))))
            suspicious["forge"]+=diagnostic["join_status"]=="JOIN_TEXT_MISMATCH_REVIEW"
            item=(rec,method,actions,attrs,snips,relation,diagnostic,rec_index)
            f_matches_before[idx].append(item)
            allowed,_=apply_join_review(idx,decision)
            if allowed: f_matches[idx].append(item)
            else: unmatched_f.append({"record":jsonable(rec),"name":card_name(rec),"reason":"reviewed_reject_join","join_review":join_review_metadata("forge",sf[idx].get("oracle_id"),reviewed_decisions)})
        elif method.startswith("ambiguous"): ambiguous.append({"source":"forge","method":method,"record":jsonable(rec)})
        else: unmatched_f.append({"record":jsonable(rec),"name":card_name(rec),"reason":method})

    for rec_index, rec in enumerate(xmage):
        idx,method=match(rec); imports,classes,snippet=java_extract(rec.get("completion",rec.get("output",all_strings(rec))))
        semantic=xmage_semantic_classes(classes)
        xmage_all_counts.update(classes); xmage_counts.update(semantic); xmage_extracts.append((rec,imports,classes,semantic,snippet))
        if idx is not None:
            relation=oracle_text_relation(rec,sf[idx]); text_counts["xmage"][relation]+=1
            diagnostic=mismatch_diagnostic("xmage",rec,sf[idx]) if relation=="MISMATCH" else {"category":None,"join_status":"JOIN_TEXT_MATCH" if relation=="MATCH" else "JOIN_TEXT_MISSING","similarity":1.0 if relation=="MATCH" else None,"notes":"Exact normalized match." if relation=="MATCH" else "Source Oracle text missing."}
            decision=None
            if relation=="MISMATCH":
                sample=mismatch_sample("xmage",rec,sf[idx],method,diagnostic,rec_index)
                mismatch_records["xmage"].append(sample)
                if diagnostic["join_status"]=="JOIN_TEXT_MISMATCH_REVIEW":
                    decision=lookup_join_decision(reviewed_decisions,sample["audit_id"])
                    if not decision: raise RuntimeError(f"No reviewed decision for suspicious join {sample['audit_id']}")
                    applied_decisions[sample["audit_id"]]=decision
                    join_audit_records.append(build_join_audit_record(sample,rec,sf[idx],decision,len(dict.fromkeys(by_name.get(norm(card_name(rec)),[])))))
            suspicious["xmage"]+=diagnostic["join_status"]=="JOIN_TEXT_MISMATCH_REVIEW"
            item=(rec,method,imports,classes,semantic,snippet,relation,diagnostic,rec_index)
            x_matches_before[idx].append(item)
            allowed,_=apply_join_review(idx,decision)
            if allowed: x_matches[idx].append(item)
            else: unmatched_x.append({"record":jsonable(rec),"name":card_name(rec),"reason":"reviewed_reject_join","join_review":join_review_metadata("xmage",sf[idx].get("oracle_id"),reviewed_decisions)})
        elif method.startswith("ambiguous"): ambiguous.append({"source":"xmage","method":method,"record":jsonable(rec)})
        else: unmatched_x.append({"record":jsonable(rec),"name":card_name(rec),"reason":method})

    expected_audit_ids=set(reviewed_decisions)
    actual_audit_ids={row["audit_id"] for row in join_audit_records}
    if len(join_audit_records)!=58 or actual_audit_ids!=expected_audit_ids:
        missing=sorted(expected_audit_ids-actual_audit_ids); extra=sorted(actual_audit_ids-expected_audit_ids)
        raise RuntimeError(f"Pinned suspicious join set differs from reviewed decisions: audited={len(join_audit_records)}, missing={missing}, extra={extra}")

    forge_mapped=Counter({t:n for t,n in forge_counts.items() if t in forge_map})
    forge_unmapped=Counter({t:n for t,n in forge_counts.items() if t not in forge_map})
    xmage_mapped=Counter({t:n for t,n in xmage_counts.items() if t in xmage_map})
    xmage_unmapped=Counter({t:n for t,n in xmage_counts.items() if t not in xmage_map})
    mapping_occurrences={
        "forge":mapping_coverage(forge_counts,forge_map),
        "xmage":mapping_coverage(xmage_counts,xmage_map),
    }

    candidates=[]; matched=[]; requirement_counts=Counter()
    mapped_cards=set(); unmapped_cards=set()
    unmapped_card_counts={"forge":Counter(),"xmage":Counter()}
    source_revisions=getattr(mine,"revisions",PINNED_REVISIONS)
    provenance={"extractor_version":EXTRACTOR_VERSION,"mapping_sha256":hashlib.sha256((ROOT/"mappings.yaml").read_bytes()).hexdigest(),"join_review_sha256":hashlib.sha256((ROOT/"reviewed_join_decisions.yaml").read_bytes()).hexdigest(),"source_set":{"scryfall":source_revisions.get("scryfall"),"forge":source_revisions.get("forge"),"xmage":source_revisions.get("xmage"),"rules":None}}

    for i,card in enumerate(sf):
        f=f_matches.get(i,[]); x=x_matches.get(i,[])
        if not (f or x): continue
        mapped=defaultdict(list); unmapped=[]
        for rec,method,actions,attrs,snips,relation,diag,rec_index in f:
            found,unknown=partition_tokens("forge",actions,forge_map,method,rec_index)
            review_metadata=join_review_metadata("forge",card.get("oracle_id"),reviewed_decisions)
            for kind,items in found.items():
                for item in items: item["oracle_text_comparison"]=relation; item.update(review_metadata)
                mapped[kind].extend(items)
            for item in unknown: item.update(review_metadata)
            unmapped.extend(unknown)
            unmapped_card_counts["forge"].update(item["token"] for item in unknown)
        for rec,method,imports,classes,semantic,snippet,relation,diag,rec_index in x:
            found,unknown=partition_tokens("xmage",semantic,xmage_map,method,rec_index)
            review_metadata=join_review_metadata("xmage",card.get("oracle_id"),reviewed_decisions)
            for kind,items in found.items():
                for item in items: item["oracle_text_comparison"]=relation; item.update(review_metadata)
                mapped[kind].extend(items)
            for item in unknown: item.update(review_metadata)
            unmapped.extend(unknown)
            unmapped_card_counts["xmage"].update(item["token"] for item in unknown)
        mapped_req=[]
        for kind,evidence in sorted(mapped.items()):
            impl=implementation_status(e["source"] for e in evidence)
            requirement_counts[impl]+=1
            mapped_req.append({"kind":kind,"evidence":evidence,"extraction_status":"AUTO_EXTRACTED","implementation_evidence":impl,"rules_evidence":"NOT_CHECKED","review_status":"UNREVIEWED"})
        if mapped_req: mapped_cards.add(i)
        if unmapped: unmapped_cards.add(i)
        bucket=resolution_bucket(True,len(mapped_req),len(unmapped),False)
        candidates.append({"oracle_id":card.get("oracle_id"),"name":card.get("name"),"provenance":provenance,"requirements":mapped_req,"unmapped_evidence":unmapped,"resolution_status":bucket,"resolution_note":"Lexical extraction does not prove semantic completeness; no card is declared fully resolved in this calibration pass." if bucket=="COMPLETENESS_UNVERIFIED" else None})

        fa=sorted({a for _,_,actions,_,_,_,_,_ in f for a in actions})
        xc=sorted({c for _,_,_,classes,_,_,_,_,_ in x for c in classes})
        matched.append({"oracle_id":card.get("oracle_id"),"name":card.get("name"),"oracle_text":card.get("oracle_text"),
            "forge":{"present":bool(f),"actions":fa,"evidence":[{"match_method":m,"oracle_text_comparison":rel,"join_diagnostic":diag,"input":r.get("input"),"snippets":sn,**join_review_metadata("forge",card.get("oracle_id"),reviewed_decisions)} for r,m,_,_,sn,rel,diag,_ in f]},
            "xmage":{"present":bool(x),"classes":xc,"evidence":[{"match_method":m,"oracle_text_comparison":rel,"join_diagnostic":diag,"prompt":r.get("prompt"),"imports":im,"snippet":sn,**join_review_metadata("xmage",card.get("oracle_id"),reviewed_decisions)} for r,m,im,_,_,sn,rel,diag,_ in x]},
            "match":{"forge":sorted({m for _,m,_,_,_,_,_,_ in f}),"xmage":sorted({m for _,m,_,_,_,_,_,_,_ in x})}})

    card_stats=summarize_card_resolution(len(sf),f_matches,x_matches,mapped_cards,unmapped_cards)
    req_stats={"total_mapped_candidates":sum(requirement_counts.values()),"multi_implementation_agreement":requirement_counts["MULTI_IMPLEMENTATION_AGREEMENT"],"forge_only":requirement_counts["FORGE_ONLY"],"xmage_only":requirement_counts["XMAGE_ONLY"]}
    req_stats["total_mapped_candidates"]=sum(req_stats[k] for k in ("multi_implementation_agreement","forge_only","xmage_only"))
    candidate_before=candidate_status_counts(sf,f_matches_before,x_matches_before,forge_map,xmage_map)
    candidate_after={"total_mapped_candidates":req_stats["total_mapped_candidates"],"multi_implementation_agreement":req_stats["multi_implementation_agreement"],"forge_only":req_stats["forge_only"],"xmage_only":req_stats["xmage_only"]}
    requirement_stats={"cards":card_stats,"requirements":req_stats,"unmapped_evidence":{"forge_tokens":sum(unmapped_card_counts["forge"].values()),"xmage_tokens":sum(unmapped_card_counts["xmage"].values()),"cards_with_unmapped_evidence":len(unmapped_cards)},"definitions":{"fully_unresolved":"External evidence is joined to a Scryfall card, but no extracted semantic token/class has a seed mapping.","partially_resolved":"At least one mapped requirement and at least one unmapped extracted semantic token/class.","fully_resolved":"No cards declared fully resolved because lexical extraction cannot prove that all semantic evidence was captured.","resolution_completeness_unverified":"At least one mapped requirement and no observed unmapped semantic token/class; completeness remains unproven."}}

    mismatch_audit=build_mismatch_audit(mismatch_records,text_counts)
    suspicious_total=sum(suspicious.values())
    action_counts=Counter(d["action"] for d in applied_decisions.values())
    result_counts=Counter(d["result"] for d in applied_decisions.values())
    result_types=("VALID_JOIN_STALE_WORDING","VALID_JOIN_FORMATTING_VARIANT","VALID_JOIN_MULTIFACE_VARIANT","VALID_JOIN_TEMPLATE_VARIANT","VALID_JOIN_OTHER","SOURCE_RECORD_WRONG_OR_CORRUPT","SOURCE_RECORD_NONSTANDARD_OR_CUSTOM","SOURCE_RECORD_INCOMPLETE","BAD_JOIN_NAME_COLLISION","BAD_JOIN_FACE_COLLISION","BAD_JOIN_OTHER","UNRESOLVED")
    join_audit_stats={"total_audited":len(join_audit_records),"by_source":{"forge":sum(r["source"]=="forge" for r in join_audit_records),"xmage":sum(r["source"]=="xmage" for r in join_audit_records)},"actions":{"KEEP_JOIN":action_counts["KEEP_JOIN"],"KEEP_WITH_FLAG":action_counts["KEEP_WITH_FLAG"],"REJECT_JOIN":action_counts["REJECT_JOIN"]},"results":{key:result_counts[key] for key in result_types},"unresolved":result_counts["UNRESOLVED"],"matching_before":{"forge_identities":len(f_matches_before),"xmage_identities":len(x_matches_before),"both_identities":len(set(f_matches_before)&set(x_matches_before))},"matching_after":{"forge_identities":len(f_matches),"xmage_identities":len(x_matches),"both_identities":len(set(f_matches)&set(x_matches))},"candidate_impact":{"before":candidate_before,"after":candidate_after}}
    unmapped_f_rows=unmapped_vocab_rows(forge_unmapped,forge_extracts,"forge")
    unmapped_x_rows=unmapped_vocab_rows(xmage_unmapped,xmage_extracts,"xmage")

    inv=inventory(rows,source_revisions)
    inv["remote_head_revisions"]=getattr(mine,"remote_revisions",{})
    field_counts=Counter(a for _,_,attrs,_ in forge_extracts for a in attrs)
    inv["datasets"]["forge"]["extraction_vocabulary"]={"actions":dict(forge_counts.most_common(50)),"fields":dict(field_counts.most_common(50))}
    inv["datasets"]["xmage"]["semantic_class_counts"]=dict(xmage_counts.most_common(100))
    write_json(OUT/"inventory.json",inv)

    def csv_counts(path,header,data):
        with path.open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f);w.writerow(header);w.writerows(data)
    csv_counts(OUT/"forge_tokens.csv",["kind","token","count"],[("forge_action",k,v) for k,v in forge_counts.most_common()]+[("forge_field",k,v) for k,v in field_counts.most_common()])
    csv_counts(OUT/"xmage_classes.csv",["category","class_name","count"],[(class_category(k),k,v) for k,v in xmage_all_counts.most_common()])
    csv_counts(OUT/"unmapped_forge_tokens.csv",["token","count","example_card_names"],unmapped_f_rows)
    csv_counts(OUT/"unmapped_xmage_classes.csv",["class","count","example_card_names"],unmapped_x_rows)
    write_json(OUT/"requirement_stats.json",requirement_stats)
    write_json(OUT/"suspicious_join_audit.json",{"source_set":source_revisions,"decision_file_sha256":provenance["join_review_sha256"],"records":sorted(join_audit_records,key=lambda r:(r["source"],r["card_name"].casefold(),r["oracle_id"]))})
    write_json(OUT/"join_audit_stats.json",join_audit_stats)
    write_json(OUT/"mapping_coverage.json",mapping_occurrences)
    write_json(OUT/"oracle_mismatch_audit.json",mismatch_audit)
    write_jsonl(OUT/"matched_cards.jsonl",matched);write_jsonl(OUT/"unmatched_forge.jsonl",unmatched_f);write_jsonl(OUT/"unmatched_xmage.jsonl",unmatched_x);write_jsonl(OUT/"ambiguous_matches.jsonl",ambiguous);write_jsonl(OUT/"requirement_candidates.jsonl",candidates)
    stats={"scryfall":len(sf),"forge":len(forge),"xmage":len(xmage),"forge_matched_records":sum(map(len,f_matches.values())),"xmage_matched_records":sum(map(len,x_matches.values())),"forge_cards":len(f_matches),"xmage_cards":len(x_matches),"both_cards":len(set(f_matches)&set(x_matches)),"unmatched_forge":len(unmatched_f),"unmatched_xmage":len(unmatched_x),"ambiguous":len(ambiguous),"oracle_text_comparison":{source:dict(counts) for source,counts in text_counts.items()},"suspicious_joins":suspicious_total,"requirements":requirement_counts}
    write_json(OUT/"stats.json",stats)
    mine.validation_inventory=generate_review_artifacts(sf,f_matches,x_matches,forge_extracts,xmage_extracts,forge_map,xmage_map,source_revisions,reviewed_decisions)
    mine.last_stats=stats
    return stats


def class_category(name):
    if name.startswith("Target"): return "Target"
    if name.startswith("Filter"): return "Filter"
    for suffix, cat in [("ReplacementEffect","ReplacementEffect"),("Ability","Ability"),("Effect","Effect"),("Cost","Cost"),("Target","Target"),("Filter","Filter"),("Condition","Condition")]:
        if name.endswith(suffix): return cat
    return "class_or_other"


def revisions():
    return dict(PINNED_REVISIONS)


def remote_revisions():
    os.environ.setdefault("HF_HOME", str(RAW / "hf-home"))
    from huggingface_hub import HfApi
    api=HfApi(); result={}
    for key,repo in SOURCES.items():
        try: result[key]=api.dataset_info(repo).sha
        except Exception: result[key]=None
    return result


def report(stats=None):
    inv=json.loads((OUT/"inventory.json").read_text(encoding="utf-8"))
    stats=stats or json.loads((OUT/"stats.json").read_text(encoding="utf-8"))
    card=json.loads((OUT/"requirement_stats.json").read_text(encoding="utf-8"))
    coverage=json.loads((OUT/"mapping_coverage.json").read_text(encoding="utf-8"))
    audit=json.loads((OUT/"oracle_mismatch_audit.json").read_text(encoding="utf-8"))
    import importlib.metadata as md
    versions={p:md.version(p) for p in ("datasets","huggingface_hub","PyYAML")}
    lines=["# Manafold CAP miner — Phase 0.1.2 Suspicious Join Audit","",f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat()} UTC","", "## Dataset inventory", ""]
    for key,d in inv["datasets"].items():
        latest=inv.get("remote_head_revisions",{}).get(key)
        state="pinned snapshot" if latest in (None,d.get("revision")) else f"pinned snapshot; current Hub head differs (`{latest}`)"
        lines += [f"### {key}: `{d['repository']}`","",f"Revision: `{d.get('revision')}` ({state}). Rows: **{d['rows']:,}**. Splits: `{d['splits']}`.",f"Columns: {', '.join('`'+c+'`' for c in d['columns'])}",""]
    lines += [f"Python package versions: `{versions}`. Cache/materialization timestamp: `{inv['generated_at_utc']}` UTC. Mining is pinned to the Phase 0.1.0 revisions listed above; if the current Hub head has moved, it is recorded but not substituted.","", "## Calibration summary", "",f"Exact-identity matching: Forge {stats['forge_cards']:,}/{stats['scryfall']:,} ({pct(stats['forge_cards'],stats['scryfall'])}); XMage {stats['xmage_cards']:,}/{stats['scryfall']:,} ({pct(stats['xmage_cards'],stats['scryfall'])}); both {stats['both_cards']:,} ({pct(stats['both_cards'],stats['scryfall'])}). Ambiguous records: {stats['ambiguous']:,}.",f"Cards with implementation evidence and at least one mapped requirement: {card['cards']['with_any_mapped_requirement']:,}/{card['cards']['with_any_external_evidence']:,} ({pct(card['cards']['with_any_mapped_requirement'],card['cards']['with_any_external_evidence'])}).",f"Seed mapping SHA-256: `{hashlib.sha256((ROOT/'mappings.yaml').read_bytes()).hexdigest()}`. Extractor version: `{EXTRACTOR_VERSION}`.","", "## Card-level resolution", "", "Card counts are distinct Scryfall Oracle identities, not requirement rows. A card with external evidence is `fully_unresolved` when none of its extracted semantic tokens/classes map; `partially_resolved` when it has both mapped and unmapped evidence. Lexical extraction cannot demonstrate completeness, so `fully_resolved` is conservatively zero. Cards with mapped evidence and no observed unmapped semantic token are shown separately as `resolution_completeness_unverified`.","",f"- Total Oracle identities: **{card['cards']['scryfall_total']:,}**",f"- With any external evidence: **{card['cards']['with_any_external_evidence']:,}**",f"- With Forge / XMage / both: **{card['cards']['with_forge_evidence']:,} / {card['cards']['with_xmage_evidence']:,} / {card['cards']['with_both_evidence']:,}**",f"- With any mapped requirement: **{card['cards']['with_any_mapped_requirement']:,}**",f"- Fully unresolved: **{card['cards']['fully_unresolved']:,}**",f"- Partially resolved: **{card['cards']['partially_resolved']:,}**",f"- Fully resolved: **{card['cards']['fully_resolved']:,}**",f"- Completeness unverified: **{card['cards']['resolution_completeness_unverified']:,}**", "", "## Requirement-level evidence", "", "These counts are mapped requirement candidates (card × generic kind), not cards. `MULTI_IMPLEMENTATION_AGREEMENT` means Forge and XMage independently expose constructs mapped by the seed map to the same generic candidate. It does not mean rules-correct, human-verified, or high-confidence. Every candidate remains `rules_evidence: NOT_CHECKED` and `review_status: UNREVIEWED`.","",f"- Total mapped candidates: **{card['requirements']['total_mapped_candidates']:,}**",f"- Multi-implementation agreement: **{card['requirements']['multi_implementation_agreement']:,}**",f"- Forge only: **{card['requirements']['forge_only']:,}**",f"- XMage only: **{card['requirements']['xmage_only']:,}**",f"- Unmapped evidence attached to matched cards: Forge {card['unmapped_evidence']['forge_tokens']:,} action occurrences; XMage {card['unmapped_evidence']['xmage_tokens']:,} semantic class occurrences; cards affected {card['unmapped_evidence']['cards_with_unmapped_evidence']:,}.","", "## Mapping coverage", "", "Coverage denominators include all records in each pinned source corpus; Forge actions count parsed action occurrences, while each XMage class counts at most once per implementation record. Structural Java bases, targets, and filters are excluded from the XMage semantic-class denominator.",""]
    for source in ("forge","xmage"):
        c=coverage[source]
        lines += [f"### {source}","",f"Unique extracted types: {c['unique_tokens']:,}; mapped: {c['mapped_unique_tokens']:,}; unmapped: {c['unmapped_unique_tokens']:,}.",f"Occurrences: {c['occurrences_mapped']:,}/{c['occurrences_total']:,} mapped ({c['occurrence_coverage_percent']:.2f}%).",""]
    lines += ["## Oracle mismatch audit","", "Identity matching remains exact and deterministic. Text similarity is used only after an exact-name/Oracle-ID join to label diagnostics; it never establishes identity. Classifier categories are hypotheses or exact-normalization diagnostics, not text repairs.","", "Calibration found that some XMage multiface prompts contain a separate `Oracle Text:` block after a second face's `Name:` and other fields. The earlier extractor could absorb that metadata into the first face's text. The 0.1.1 parser now stops at prompt field boundaries and combines all face text blocks. In this pinned run, the prior 80 `LIKELY_PROMPT_EXTRACTION_ARTIFACT` records disappear; 144 source texts now exactly match the combined face representation. No dataset text was changed.",""]
    for source in ("forge","xmage"):
        a=audit["sources"][source]
        lines += [f"### {source}","",f"Mismatches: {a['matched_text_mismatches']:,}; assigned a diagnostic category: {a['classified_count']:,} ({a['classified_percentage']:.2f}%); text-diagnostic `UNCLASSIFIED`: {a['unclassified_count']:,}; sent to the Phase 0.1.2 identity audit: {a['suspicious_joins']:,}.","","| category | count | % of mismatches |","|---|---:|---:|"]
        lines += [f"| `{category}` | {v['count']:,} | {v['percentage_of_mismatches']:.2f}% |" for category,v in a["categories"].items()]
        lines += [""]
    mismatch_total=sum(audit["sources"][s]["matched_text_mismatches"] for s in ("forge","xmage"))
    unclassified_total=sum(audit["sources"][s]["unclassified_count"] for s in ("forge","xmage"))
    explained=mismatch_total-unclassified_total
    exact_explained=sum(audit["sources"][s]["exactly_explained_count"] for s in ("forge","xmage"))
    lines += [f"Exact diagnostic normalization explains {exact_explained:,}/{mismatch_total:,} mismatches ({pct(exact_explained,mismatch_total)}): equality after reminder-text removal, card-name/self-template normalization, or face-text comparison. Another {explained-exact_explained:,} receive a heuristic diagnostic such as likely stale wording or possible bad join. In total {explained:,}/{mismatch_total:,} ({pct(explained,mismatch_total)}) have a non-`UNCLASSIFIED` category; **{unclassified_total:,}** remain unclassified by that text heuristic. All 58 exact-identity cases were then individually classified in `JOIN_AUDIT.md` and `data/output/suspicious_join_audit.json`. Categories and up to 20 sorted examples per category are in `data/output/oracle_mismatch_audit.json`.","", "## Top unmapped vocabulary", "", "Examples are the first five distinct names in normalized alphabetical order; token counts are deterministic corpus occurrence counts.","", "### Forge actions", ""]
    lines += csv_markdown(OUT/"unmapped_forge_tokens.csv",20)
    lines += ["", "### XMage semantic classes", ""]
    lines += csv_markdown(OUT/"unmapped_xmage_classes.csv",20)
    join_stats=json.loads((OUT/"join_audit_stats.json").read_text(encoding="utf-8"))
    lines += ["", "## Phase 0.1.2 join decisions", "",f"The pinned suspicious set contains {join_stats['total_audited']} individually reviewed records: {join_stats['actions']}. No join was rejected. {join_stats['unresolved']} decisions remain unresolved. Nine XMage records are retained with warnings because their type-line dash is mojibake; warning metadata is attached to their matched evidence.",f"Identity counts and mapped candidate counts did not change: before/after Forge {join_stats['matching_before']['forge_identities']}/{join_stats['matching_after']['forge_identities']}, XMage {join_stats['matching_before']['xmage_identities']}/{join_stats['matching_after']['xmage_identities']}, both {join_stats['matching_before']['both_identities']}/{join_stats['matching_after']['both_identities']}; mapped candidates {join_stats['candidate_impact']['before']['total_mapped_candidates']}/{join_stats['candidate_impact']['after']['total_mapped_candidates']}.","", "## Interpretation and next decision", "",f"The 0.1.1 seed mappings changed candidate-level cross-engine agreement from the 0.1.0 baseline of 2,962 to {card['requirements']['multi_implementation_agreement']:,}. This is a count of mapped candidate pairs, not a correctness score.","All audited identities were supported by an exact unique normalized card name and matching card context. Oracle wording variants are retained; nine encoding warnings remain visible on XMage evidence. No name collision, face collision, or matching-policy defect was found. The audited identity joins are suitable for Phase 0.2 while preserving those warnings.","", "No rules validation, eligibility policy, or CAP integration was added. Forge and XMage remain implementation evidence, not semantic authority. No LLM or embeddings are used.",""]
    (ROOT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    write_join_audit_report(join_stats)
    write_validation_report()


def write_join_audit_report(stats):
    rows=json.loads((OUT/"suspicious_join_audit.json").read_text(encoding="utf-8"))["records"]
    stale=[r for r in rows if r["audit_result"]=="VALID_JOIN_STALE_WORDING"]
    flagged=[r for r in rows if r["action"]=="KEEP_WITH_FLAG"]
    rejected=[r for r in rows if r["action"]=="REJECT_JOIN"]
    lines=["# Phase 0.1.2 — Suspicious Join Audit","",f"Pinned input revisions: Scryfall `{PINNED_REVISIONS['scryfall']}`, Forge `{PINNED_REVISIONS['forge']}`, XMage `{PINNED_REVISIONS['xmage']}`.","", "## Summary", "",f"Audited {stats['total_audited']} records: Forge {stats['by_source']['forge']}, XMage {stats['by_source']['xmage']}. Decisions: `{stats['actions']}`. Results: `{ {k:v for k,v in stats['results'].items() if v} }`. Unresolved: {stats['unresolved']}.","", "All 58 audit candidates had an exact normalized name that selected one Scryfall identity. Text similarity was diagnostic only. No record was rejected; join review is not validation of requirement semantics.","", "## Rejected joins", ""]
    lines += [f"- `{r['source']}` `{r['card_name']}` (`{r['oracle_id']}`): {r['reason']}" for r in rejected] or ["None."]
    lines += ["", "## Flagged joins", ""]
    lines += [f"- `{r['source']}` `{r['card_name']}` (`{r['oracle_id']}`): {r['reason']}" for r in flagged] or ["None."]
    lines += ["", "## Valid stale/variant joins", "",f"{len(stale)} records were retained as `VALID_JOIN_STALE_WORDING`. The source records use historical Oracle wording such as printed card names for self-reference, “enters the battlefield,” or reminder-text variants. Exact unique names and the available type/mana context agree with the pinned Scryfall identity. Representative records:",""]
    lines += [f"- `{r['source']}` `{r['card_name']}` — {r['reason']}" for r in stale[:8]]
    lines += ["", "## Systematic issues found", "", "No normalized-name collision or multiface collision occurred among the 58. All were `normalized_name` joins; the name index resolved each to one Scryfall row, and no Oracle ID was available in the external records. All source type lines match Scryfall except nine XMage prompts whose em dash is encoded as the mojibake sequence U+00E2 U+20AC U+201D. Those nine have matching type words after that known encoding normalization and retain matching names/mana context; they are `SOURCE_RECORD_WRONG_OR_CORRUPT` with `KEEP_WITH_FLAG`. No bug was found in card-name extraction, Oracle-text extraction, face indexing, ambiguity detection, or Oracle-ID precedence.","", "## Matching changes", "",f"Before / after distinct identities — Forge: {stats['matching_before']['forge_identities']} / {stats['matching_after']['forge_identities']}; XMage: {stats['matching_before']['xmage_identities']} / {stats['matching_after']['xmage_identities']}; both: {stats['matching_before']['both_identities']} / {stats['matching_after']['both_identities']}.",f"Mapped candidates — total {stats['candidate_impact']['before']['total_mapped_candidates']} / {stats['candidate_impact']['after']['total_mapped_candidates']}; multi-implementation {stats['candidate_impact']['before']['multi_implementation_agreement']} / {stats['candidate_impact']['after']['multi_implementation_agreement']}. No rejected joins means downstream counts are unchanged. `KEEP_WITH_FLAG` metadata is attached to the affected matched evidence and requirement evidence.","", "## Recommendation for Phase 0.2", "", "READY. The exact-name joins in this narrowly audited set are supported by unique identity and card context; none should be excluded. Carry the nine XMage encoding warnings forward. This decision is about identity only and does not assert that source Oracle wording or extracted implementation semantics are correct.",""]
    (ROOT/"JOIN_AUDIT.md").write_text("\n".join(lines),encoding="utf-8")


def write_validation_report():
    inv=json.loads((OUT/"pattern_inventory.json").read_text(encoding="utf-8"))
    patterns=inv["patterns"]; counts=Counter(p["risk"] for p in patterns)
    second=sum(p["second_review_required_samples"] for p in patterns)
    availability=inv["oracle_text_availability"]
    warnings=inv["join_quality_warnings"]
    methods=inv["interval_method_counts"]
    projection=__import__("yaml").safe_load((ROOT/"requirement_evidence_projection.yaml").read_text(encoding="utf-8"))
    naturally=inv["naturally_sampled_warning_count"]; forced=inv["forced_warning_count"]
    warning_covered=sum(w["coverage_status"] in {"COVERED_BY_PROBABILITY_SAMPLE","COVERED_BY_FORCED_AUDIT"} and bool(w["relevant_pattern_ids"]) for w in warnings)
    lines=["# Phase 0.2A.1 — Statistical & Sampling Corrections","", "## Summary", "",f"Primary probability sample: {inv['probability_sample_count']} items; forced join-warning audit: {inv['forced_audit_sample_count']}; total review packet items: {inv['total_review_packet_items']}. The original LOW-risk 60 and all 460 Phase 0.2A probability sample IDs are preserved.",f"Selected patterns: {len(patterns)} (LOW {counts['LOW']}, MEDIUM {counts['MEDIUM']}, HIGH {counts['HIGH']}); blind second review is assigned to {second} primary probability items.",f"Pinned source revisions are Scryfall `{PINNED_REVISIONS['scryfall']}`, Forge `{PINNED_REVISIONS['forge']}`, XMage `{PINNED_REVISIONS['xmage']}`. Extractor `{VALIDATION_EXTRACTOR_VERSION}`; mapping SHA-256 `{inv['validation_scope']['mapping_sha256']}`.","", "No real review results were consumed. No semantic precision is calculated. No mappings, rules evidence, or CAP eligibility were changed.","", "## Statistical sampling corrections", "",f"Primary probability items remain distinct from forced audit items. `total_samples` and all pattern sample-size/interval calculations refer only to the {inv['probability_sample_count']} probability items. The additional {inv['forced_audit_sample_count']} forced audit items have `selection_basis: FORCED_FLAGGED_JOIN_AUDIT` and are excluded from every statistical denominator.",f"The existing 460 probability sample IDs match the captured Phase 0.2A baseline digest `{PHASE_0_2A_SAMPLE_IDS_SHA256}`; the LOW 60 match `{PHASE_0_2A_LOW_SAMPLE_IDS_SHA256}`. Existing Reviewer-A decisions can reuse those IDs.","", "## Finite population handling", "",f"Method selector threshold: sampling fraction <= {plan_threshold(inv):.0%} uses `WILSON_BINOMIAL`; larger fractions use `FINITE_POPULATION_HYPERGEOMETRIC` exact inversion under hypergeometric sampling without replacement. This is a planned method only; accepted counts are null, so no interval estimate or bound is calculated.",f"Patterns by planned method: Wilson/binomial {methods['WILSON_BINOMIAL']}; finite-population hypergeometric {methods['FINITE_POPULATION_HYPERGEOMETRIC']}.","","| pattern | N | probability n | sampling fraction | planned interval | forced n |","|---|---:|---:|---:|---|---:|"]
    lines += [f"| `{p['pattern_id']}` | {p['population_size']:,} | {p['probability_sample_size']} | {p['sampling_fraction']:.5f} | `{p['planned_interval_method']}` | {p['forced_audit_sample_size']} |" for p in patterns]
    lines += ["", "The standard-library hypergeometric interval helper in `src/cap_miner.py` is prepared for later result aggregation. Synthetic tests cover bounds and census collapse. It is not run on absent review data.","", "## Known warning coverage", "",f"Known Phase 0.1.2 warning records: {inv['known_join_warning_count']}. Naturally sampled: {naturally}. Forced audit samples added: {forced}. Of the warnings relevant to selected patterns, {warning_covered} have review coverage. Other warnings remain registered but do not relate to these selected patterns.","","| card | relevant selected patterns | coverage | sample ID |","|---|---|---|---|"]
    lines += [f"| `{w['card_name']}` | {', '.join(w['relevant_pattern_ids']) or 'none'} | `{w['coverage_status']}` | `{w['forced_sample_id'] or ', '.join(w['review_sample_ids'])}` |" for w in warnings]
    lines += ["", "Forced records carry their reviewed join status/reason and use stable IDs. They are audit coverage, not representative observations. Warnings outside the selected pattern populations stay in the warning register and are not forced into unrelated pattern reviews.","", "## Oracle text availability", "",f"Counts below use exactly the {availability['primary_sample_count']} primary probability items; forced audit items are excluded. Source availability is distinct from canonical Scryfall text.",f"- Pattern-source Oracle text: PRESENT {availability['source_oracle_text_status']['PRESENT']}; MISSING {availability['source_oracle_text_status']['MISSING']}.",f"- Source-by-engine rows: Forge PRESENT {availability['source_oracle_text_by_engine']['forge']['PRESENT']}, MISSING {availability['source_oracle_text_by_engine']['forge']['MISSING']}, NOT_AVAILABLE {availability['source_oracle_text_by_engine']['forge']['NOT_AVAILABLE']}; XMage PRESENT {availability['source_oracle_text_by_engine']['xmage']['PRESENT']}, MISSING {availability['source_oracle_text_by_engine']['xmage']['MISSING']}, NOT_AVAILABLE {availability['source_oracle_text_by_engine']['xmage']['NOT_AVAILABLE']}.",f"- Canonical parent text available: {availability['canonical_parent_text_available']}.",f"- Canonical face text available: {availability['canonical_face_text_available']}.",f"- Canonical parent and face text available: {availability['canonical_oracle_text_status']['PARENT_AND_FACE_TEXT_AVAILABLE']}.",f"- Canonical text completely missing: {availability['canonical_text_missing']}.",f"- Source text missing while canonical face text exists: {availability['source_missing_but_canonical_face_available']}.","","| pattern | primary n | source PRESENT | source MISSING | parent text | face text | canonical missing |","|---|---:|---:|---:|---:|---:|---:|"]
    lines += [f"| `{pattern}` | {v['sample_count']} | {v['source_text_present']} | {v['source_text_missing']} | {v['canonical_parent_text_available']} | {v['canonical_face_text_available']} | {v['canonical_text_missing']} |" for pattern,v in availability['by_pattern'].items()]
    lines += ["", "Each review item carries `source_oracle_text_status`, per-engine source statuses, `canonical_oracle_text_status`, and a named `canonical_oracle.faces` array. `source_oracle_text_status: MISSING` does not imply missing canonical support. `rules_evidence` remains `NOT_CHECKED`; Oracle text is not Comprehensive Rules evidence.","", "## Requirement evidence projection", "",f"`requirement_evidence_projection.yaml` lists separate source mapping paths for {len(projection['requirements'])} Requirements. Pattern precision is not averaged, summed, minimized, maximized, or combined. When both engines support a card candidate, retain Forge and XMage path results separately and record the cross pattern as `CROSS_IMPLEMENTATION_CORROBORATION` only.","", "## Existing review compatibility", "", "`EXISTING_REVIEW_COMPATIBILITY = PRESERVED`. A runtime guard verifies the complete 460-ID digest and the LOW-risk 60-ID digest before writing the packet. Forced audit items are appended separately; probability rows are not regenerated with altered IDs.","", "## Validation state and next review", "", "No real Reviewer-A decisions were consumed. No real precision or reviewer agreement is available. Pattern statuses remain `AWAITING_REVIEW`; `patterns_validated = 0`; no CAP eligibility decision exists.","", "Review `data/output/review_samples.jsonl` for probability samples. Review `data/output/forced_audit_samples.jsonl` separately for forced warning audits. Record results in separate reviewer YAML files copied from `review_results.example.yaml`; do not show Reviewer A's answers to Reviewer B. Use only `selection_basis: PROBABILITY_SAMPLE` for later precision inference. Keep forced audit findings separate.","", "Phase 0.2B should report source-path validation profiles rather than one synthetic Requirement precision. For a future primary estimate, count `CORRECT` as accepted and decisive labels (`TOO_BROAD`, `TOO_NARROW`, `CONTEXT_DEPENDENT`, `WRONG`) as non-accepts; report `AMBIGUOUS`, `SOURCE_EVIDENCE_INSUFFICIENT`, and reviewer disagreement separately. Exclude disagreements until adjudicated. No such aggregation is implemented here.",""]
    rendered="\n".join(lines)
    if inv["forced_audit_sample_count"]==1:
        rendered=rendered.replace("The additional 1 forced audit items have", "The single forced audit item has")
        rendered=rendered.replace("The single forced audit item has `selection_basis: FORCED_FLAGGED_JOIN_AUDIT` and are excluded", "The single forced audit item has `selection_basis: FORCED_FLAGGED_JOIN_AUDIT`; it is excluded")
    (ROOT/"VALIDATION_REPORT.md").write_text(rendered,encoding="utf-8")


def plan_threshold(inventory):
    return inventory["sampling"].get("interval_method_threshold",0.05)


def pct(n,d): return f"{(100*n/d if d else 0):.2f}%"
def first_forge_excerpt(record):
    evidence=record.get("forge",{}).get("evidence",[])
    snippets=evidence[0].get("snippets",[]) if evidence else []
    return re.sub(r"\s+"," ",snippets[0])[:150] if snippets else "no extracted action line"
def first_xmage_excerpt(record):
    evidence=record.get("xmage",{}).get("evidence",[])
    snippet=evidence[0].get("snippet","") if evidence else ""
    return re.sub(r"\s+"," ",snippet)[:150] if snippet else "no extracted implementation excerpt"
def table_rows(path, limit, kind=None):
    if not path.exists(): return ["(not available)"]
    with path.open(encoding="utf-8") as f: rows=list(csv.DictReader(f))
    if kind: rows=[r for r in rows if r.get("kind")==kind]
    rows=rows[:limit]
    return ["| token | count |", "|---|---:|"]+[f"| `{r.get('token',r.get('class_name'))}` | {r['count']} |" for r in rows]


def csv_markdown(path, limit):
    with path.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))[:limit]
    if not rows: return "(none)"
    header=list(rows[0])
    return ["| "+" | ".join(header)+" |","|"+"|".join("---" for _ in header)+"|"]+["| "+" | ".join(str(r.get(k,"")) for k in header)+" |" for r in rows]


def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=["download","inspect","mine","report","all"]);args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);RAW.mkdir(parents=True,exist_ok=True)
    if args.command in {"download","inspect","mine","all"}:
        loaded=load_sources(); rows=dataset_rows(loaded); rev=revisions();mine.revisions=rev;mine.remote_revisions=remote_revisions()
        if args.command in {"download","inspect"}:
            write_json(OUT/"inventory.json",inventory(rows,rev))
        if args.command in {"mine","all"}: stats=mine(rows)
        else: stats=None
    else: stats=None
    if args.command in {"report","all"}: report(stats)
    print(f"Completed {args.command}. Outputs: {OUT}")

if __name__ == "__main__": main()
