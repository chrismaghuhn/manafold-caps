"""Deterministic, deliberately small MTG implementation-evidence miner."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import hashlib
import json
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
EXTRACTOR_VERSION = "0.1.1"
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


def mismatch_sample(source, record, card, method, diagnostic):
    return {"source":source,"card_name":card.get("name"),"oracle_id":card.get("oracle_id"),"match_method":method,
            "current_scryfall_text":scryfall_text(card),"source_text":oracle_text(record),
            "category":diagnostic["category"],"join_status":diagnostic["join_status"],"similarity":diagnostic.get("similarity"),
            "token_overlap":diagnostic.get("token_overlap"),"notes":diagnostic["notes"]}


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
        oid = record.get("oracle_id") or record.get("oracleId")
        if oid and str(oid) in by_id:
            inds = by_id[str(oid)]
            return (inds[0], "oracle_id") if len(inds) == 1 else (None, "ambiguous_oracle_id")
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
    forge_counts=Counter(); xmage_counts=Counter(); xmage_all_counts=Counter()
    forge_extracts=[]; xmage_extracts=[]
    f_matches=defaultdict(list); x_matches=defaultdict(list)
    unmatched_f=[]; unmatched_x=[]; ambiguous=[]
    mismatch_records={"forge":[],"xmage":[]}; text_counts={"forge":Counter(),"xmage":Counter()}
    suspicious=Counter()

    for rec_index, rec in enumerate(forge):
        idx,method=match(rec); actions,attrs,snips=forge_extract(rec.get("output",all_strings(rec)))
        forge_counts.update(actions); forge_extracts.append((rec,actions,attrs,snips))
        if idx is not None:
            relation=oracle_text_relation(rec,sf[idx]); text_counts["forge"][relation]+=1
            diagnostic=mismatch_diagnostic("forge",rec,sf[idx]) if relation=="MISMATCH" else {"category":None,"join_status":"JOIN_TEXT_MATCH" if relation=="MATCH" else "JOIN_TEXT_MISSING","similarity":1.0 if relation=="MATCH" else None,"notes":"Exact normalized match." if relation=="MATCH" else "Source Oracle text missing."}
            if relation=="MISMATCH": mismatch_records["forge"].append(mismatch_sample("forge",rec,sf[idx],method,diagnostic))
            suspicious["forge"]+=diagnostic["join_status"]=="JOIN_TEXT_MISMATCH_REVIEW"
            f_matches[idx].append((rec,method,actions,attrs,snips,relation,diagnostic,rec_index))
        elif method.startswith("ambiguous"): ambiguous.append({"source":"forge","method":method,"record":jsonable(rec)})
        else: unmatched_f.append({"record":jsonable(rec),"name":card_name(rec),"reason":method})

    for rec_index, rec in enumerate(xmage):
        idx,method=match(rec); imports,classes,snippet=java_extract(rec.get("completion",rec.get("output",all_strings(rec))))
        semantic=xmage_semantic_classes(classes)
        xmage_all_counts.update(classes); xmage_counts.update(semantic); xmage_extracts.append((rec,imports,classes,semantic,snippet))
        if idx is not None:
            relation=oracle_text_relation(rec,sf[idx]); text_counts["xmage"][relation]+=1
            diagnostic=mismatch_diagnostic("xmage",rec,sf[idx]) if relation=="MISMATCH" else {"category":None,"join_status":"JOIN_TEXT_MATCH" if relation=="MATCH" else "JOIN_TEXT_MISSING","similarity":1.0 if relation=="MATCH" else None,"notes":"Exact normalized match." if relation=="MATCH" else "Source Oracle text missing."}
            if relation=="MISMATCH": mismatch_records["xmage"].append(mismatch_sample("xmage",rec,sf[idx],method,diagnostic))
            suspicious["xmage"]+=diagnostic["join_status"]=="JOIN_TEXT_MISMATCH_REVIEW"
            x_matches[idx].append((rec,method,imports,classes,semantic,snippet,relation,diagnostic,rec_index))
        elif method.startswith("ambiguous"): ambiguous.append({"source":"xmage","method":method,"record":jsonable(rec)})
        else: unmatched_x.append({"record":jsonable(rec),"name":card_name(rec),"reason":method})

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
    provenance={"extractor_version":EXTRACTOR_VERSION,"mapping_sha256":hashlib.sha256((ROOT/"mappings.yaml").read_bytes()).hexdigest(),"source_set":{"scryfall":source_revisions.get("scryfall"),"forge":source_revisions.get("forge"),"xmage":source_revisions.get("xmage"),"rules":None}}

    for i,card in enumerate(sf):
        f=f_matches.get(i,[]); x=x_matches.get(i,[])
        if not (f or x): continue
        mapped=defaultdict(list); unmapped=[]
        for rec,method,actions,attrs,snips,relation,diag,rec_index in f:
            found,unknown=partition_tokens("forge",actions,forge_map,method,rec_index)
            for kind,items in found.items():
                for item in items: item["oracle_text_comparison"]=relation
                mapped[kind].extend(items)
            unmapped.extend(unknown)
            unmapped_card_counts["forge"].update(item["token"] for item in unknown)
        for rec,method,imports,classes,semantic,snippet,relation,diag,rec_index in x:
            found,unknown=partition_tokens("xmage",semantic,xmage_map,method,rec_index)
            for kind,items in found.items():
                for item in items: item["oracle_text_comparison"]=relation
                mapped[kind].extend(items)
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
            "forge":{"present":bool(f),"actions":fa,"evidence":[{"match_method":m,"oracle_text_comparison":rel,"join_diagnostic":diag,"input":r.get("input"),"snippets":sn} for r,m,_,_,sn,rel,diag,_ in f]},
            "xmage":{"present":bool(x),"classes":xc,"evidence":[{"match_method":m,"oracle_text_comparison":rel,"join_diagnostic":diag,"prompt":r.get("prompt"),"imports":im,"snippet":sn} for r,m,im,_,_,sn,rel,diag,_ in x]},
            "match":{"forge":sorted({m for _,m,_,_,_,_,_,_ in f}),"xmage":sorted({m for _,m,_,_,_,_,_,_,_ in x})}})

    card_stats=summarize_card_resolution(len(sf),f_matches,x_matches,mapped_cards,unmapped_cards)
    req_stats={"total_mapped_candidates":sum(requirement_counts.values()),"multi_implementation_agreement":requirement_counts["MULTI_IMPLEMENTATION_AGREEMENT"],"forge_only":requirement_counts["FORGE_ONLY"],"xmage_only":requirement_counts["XMAGE_ONLY"]}
    req_stats["total_mapped_candidates"]=sum(req_stats[k] for k in ("multi_implementation_agreement","forge_only","xmage_only"))
    requirement_stats={"cards":card_stats,"requirements":req_stats,"unmapped_evidence":{"forge_tokens":sum(unmapped_card_counts["forge"].values()),"xmage_tokens":sum(unmapped_card_counts["xmage"].values()),"cards_with_unmapped_evidence":len(unmapped_cards)},"definitions":{"fully_unresolved":"External evidence is joined to a Scryfall card, but no extracted semantic token/class has a seed mapping.","partially_resolved":"At least one mapped requirement and at least one unmapped extracted semantic token/class.","fully_resolved":"No cards declared fully resolved because lexical extraction cannot prove that all semantic evidence was captured.","resolution_completeness_unverified":"At least one mapped requirement and no observed unmapped semantic token/class; completeness remains unproven."}}

    mismatch_audit=build_mismatch_audit(mismatch_records,text_counts)
    suspicious_total=sum(suspicious.values())
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
    write_json(OUT/"mapping_coverage.json",mapping_occurrences)
    write_json(OUT/"oracle_mismatch_audit.json",mismatch_audit)
    write_jsonl(OUT/"matched_cards.jsonl",matched);write_jsonl(OUT/"unmatched_forge.jsonl",unmatched_f);write_jsonl(OUT/"unmatched_xmage.jsonl",unmatched_x);write_jsonl(OUT/"ambiguous_matches.jsonl",ambiguous);write_jsonl(OUT/"requirement_candidates.jsonl",candidates)
    stats={"scryfall":len(sf),"forge":len(forge),"xmage":len(xmage),"forge_matched_records":sum(map(len,f_matches.values())),"xmage_matched_records":sum(map(len,x_matches.values())),"forge_cards":len(f_matches),"xmage_cards":len(x_matches),"both_cards":len(set(f_matches)&set(x_matches)),"unmatched_forge":len(unmatched_f),"unmatched_xmage":len(unmatched_x),"ambiguous":len(ambiguous),"oracle_text_comparison":{source:dict(counts) for source,counts in text_counts.items()},"suspicious_joins":suspicious_total,"requirements":requirement_counts}
    write_json(OUT/"stats.json",stats)
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
    lines=["# Manafold CAP miner — Phase 0.1.1 Evidence Calibration","",f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat()} UTC","", "## Dataset inventory", ""]
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
        lines += [f"### {source}","",f"Mismatches: {a['matched_text_mismatches']:,}; assigned a diagnostic category: {a['classified_count']:,} ({a['classified_percentage']:.2f}%); `UNCLASSIFIED`: {a['unclassified_count']:,}; suspicious joins requiring manual review: {a['suspicious_joins']:,}.","","| category | count | % of mismatches |","|---|---:|---:|"]
        lines += [f"| `{category}` | {v['count']:,} | {v['percentage_of_mismatches']:.2f}% |" for category,v in a["categories"].items()]
        lines += [""]
    mismatch_total=sum(audit["sources"][s]["matched_text_mismatches"] for s in ("forge","xmage"))
    unclassified_total=sum(audit["sources"][s]["unclassified_count"] for s in ("forge","xmage"))
    explained=mismatch_total-unclassified_total
    exact_explained=sum(audit["sources"][s]["exactly_explained_count"] for s in ("forge","xmage"))
    lines += [f"Exact diagnostic normalization explains {exact_explained:,}/{mismatch_total:,} mismatches ({pct(exact_explained,mismatch_total)}): equality after reminder-text removal, card-name/self-template normalization, or face-text comparison. Another {explained-exact_explained:,} receive a heuristic diagnostic such as likely stale wording or possible bad join. In total {explained:,}/{mismatch_total:,} ({pct(explained,mismatch_total)}) have a non-`UNCLASSIFIED` category; **{unclassified_total:,}** remain unclassified. Heuristic categories are not confirmed root causes. Categories and up to 20 sorted examples per category are in `data/output/oracle_mismatch_audit.json`.","", "## Top unmapped vocabulary", "", "Examples are the first five distinct names in normalized alphabetical order; token counts are deterministic corpus occurrence counts.","", "### Forge actions", ""]
    lines += csv_markdown(OUT/"unmapped_forge_tokens.csv",20)
    lines += ["", "### XMage semantic classes", ""]
    lines += csv_markdown(OUT/"unmapped_xmage_classes.csv",20)
    lines += ["", "## Vocabulary overview", "", "Forge action and `$` field counts are in `forge_tokens.csv`; XMage class counts (including structural classes) are in `xmage_classes.csv`. No fuzzy match was used as identity evidence.","", "## Interpretation and next decision", "",f"The new seed mappings changed candidate-level cross-engine agreement from the 0.1.0 baseline of 2,962 to {card['requirements']['multi_implementation_agreement']:,} ({card['requirements']['multi_implementation_agreement']-2962:+,}; {(100*(card['requirements']['multi_implementation_agreement']/2962-1)) if 2962 else 0:+.1f}%). This is a count of mapped candidate pairs, not a correctness score.",f"Exact-name joins with text mismatches flagged for review total {stats.get('suspicious_joins',0):,} across both sources. `oracle_mismatch_audit.json` retains raw current/source text for inspection.","", "This pass only recalibrates deterministic extraction, evidence retention, and seed mappings. It does not fetch rules or official rulings and does not decide CAP eligibility. Forge and XMage remain implementation evidence, not semantic authority. No LLM or embeddings are used.",""]
    (ROOT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")


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
