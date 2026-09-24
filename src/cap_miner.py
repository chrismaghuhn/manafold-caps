"""Deterministic, deliberately small MTG implementation-evidence miner."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
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
        m=re.search(r"(?im)^\s*Oracle Text:\s*(.*?)(?=^\s*(?:Colors|Color Identity|Keywords|Rarity|Power|Toughness|Loyalty|Defense):|\Z)",value,re.S)
        if m: return m.group(1).strip()
    return ""


def oracle_text_relation(source_record, scryfall_card):
    source=norm(oracle_text(source_record))
    if not source: return "MISSING"
    canonical=[scryfall_card.get("oracle_text") or ""]
    canonical.extend(face.get("oracle_text","") for face in (scryfall_card.get("card_faces") or []) if isinstance(face,dict))
    return "MATCH" if source in {norm(t) for t in canonical if t} else "MISMATCH"


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
        loaded[key] = load_dataset(repo, cache_dir=str(RAW / "hf"))
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
                exact = [i for i in cand if norm(sf[i].get("oracle_text")) == txt or any(norm(f.get("oracle_text")) == txt for f in (sf[i].get("card_faces") or []) if isinstance(f, dict))]
                unique=select_unambiguous(exact)
                if unique is not None: return unique, "normalized_name_and_oracle_text"
            return None, "ambiguous_normalized_name"
        txt = norm(oracle_text(record))
        if txt:
            exact = by_nt.get((name, txt), [])
            if len(exact) == 1: return exact[0], "normalized_name_and_oracle_text"
            if len(exact) > 1: return None, "ambiguous_normalized_name_and_oracle_text"
        return None, "unmatched"

    forge_counts, xmage_counts, f_matches, x_matches = Counter(), Counter(), defaultdict(list), defaultdict(list)
    unmatched_f, unmatched_x, ambiguous = [], [], []
    text_audit={"forge":Counter(),"xmage":Counter()}
    forge_extracts, x_extracts = [], []
    for rec in forge:
        idx, method = match(rec); acts, at, snips = forge_extract(rec.get("output", all_strings(rec)))
        forge_counts.update(acts); forge_extracts.append((acts, at, snips))
        if idx is not None:
            f_matches[idx].append((rec, method, acts, at, snips))
            text_audit["forge"][oracle_text_relation(rec,sf[idx])]+=1
        elif method.startswith("ambiguous"): ambiguous.append({"source":"forge","method":method,"record":jsonable(rec)})
        else: unmatched_f.append({"record":jsonable(rec),"name":card_name(rec),"reason":method})
    for rec in xmage:
        idx, method = match(rec); imports, classes, snippet = java_extract(rec.get("completion", rec.get("output", all_strings(rec))))
        xmage_counts.update(classes); x_extracts.append((imports, classes))
        if idx is not None:
            x_matches[idx].append((rec, method, imports, classes, snippet))
            text_audit["xmage"][oracle_text_relation(rec,sf[idx])]+=1
        elif method.startswith("ambiguous"): ambiguous.append({"source":"xmage","method":method,"record":jsonable(rec)})
        else: unmatched_x.append({"record":jsonable(rec),"name":card_name(rec),"reason":method})

    mapping = read_mapping(); candidates=[]; matched=[]; req_counts=Counter()
    source_revisions=getattr(mine,"revisions",{})
    provenance={"extractor_version":"0.1.0","mapping_sha256":hashlib.sha256((ROOT/"mappings.yaml").read_bytes()).hexdigest(),"source_set":{"scryfall":source_revisions.get("scryfall"),"forge":source_revisions.get("forge"),"xmage":source_revisions.get("xmage"),"rules":None}}
    for i, card in enumerate(sf):
        f = f_matches.get(i, []); x = x_matches.get(i, [])
        if f or x:
            fa = sorted({a for _,_,acts,_,_ in f for a in acts}); xc = sorted({c for _,_,_,cs,_ in x for c in cs})
            matched.append({"oracle_id":card.get("oracle_id"),"name":card.get("name"),"oracle_text":card.get("oracle_text"),
                "forge":{"present":bool(f),"actions":fa,"evidence":[{"match_method":m,"oracle_text_comparison":oracle_text_relation(r,card),"input":r.get("input"),"snippets":sn} for r,m,_,_,sn in f]},
                "xmage":{"present":bool(x),"classes":xc,"evidence":[{"match_method":m,"oracle_text_comparison":oracle_text_relation(r,card),"prompt":r.get("prompt"),"imports":im,"snippet":sn} for r,m,im,_,sn in x]},
                "match":{"forge":sorted({m for _,m,_,_,_ in f}),"xmage":sorted({m for _,m,_,_,_ in x})}})
        evidence=defaultdict(list)
        for _,_,acts,_,_ in f:
            for token in acts:
                kind=mapping.get("forge",{}).get(token)
                if kind: evidence[kind].append({"source":"forge","token":token})
        for _,_,_,classes,_ in x:
            for token in classes:
                kind=mapping.get("xmage",{}).get(token)
                if kind: evidence[kind].append({"source":"xmage","token":token})
        if evidence:
            req=[]
            for kind, ev in sorted(evidence.items()):
                sources={e["source"] for e in ev}
                impl_status=implementation_status(sources)
                req_counts[impl_status]+=1
                req.append({"kind":kind,"evidence":ev,"extraction_status":"AUTO_EXTRACTED","implementation_evidence":impl_status,"rules_evidence":"NOT_CHECKED","review_status":"UNREVIEWED"})
            candidates.append({"oracle_id":card.get("oracle_id"),"name":card.get("name"),"provenance":provenance,"requirements":req})
        elif f or x:
            unresolved=[]
            unresolved.extend({"source":"forge","token":t} for _,_,acts,_,_ in f for t in acts)
            unresolved.extend({"source":"xmage","token":t} for _,_,_,classes,_ in x for t in classes)
            req_counts["UNRESOLVED"]+=1
            candidates.append({"oracle_id":card.get("oracle_id"),"name":card.get("name"),"provenance":provenance,"requirements":[{"kind":"unresolved","evidence":unresolved[:100],"extraction_status":"UNRESOLVED","implementation_evidence":"NONE","rules_evidence":"NOT_CHECKED","review_status":"UNREVIEWED"}]})
    inv = inventory(rows, getattr(mine,"revisions",{}))
    field_counts=Counter(a for _,at,_ in forge_extracts for a in at)
    inv["datasets"]["forge"]["extraction_vocabulary"] = {"actions":dict(forge_counts.most_common(50)),"fields":dict(field_counts.most_common(50))}
    write_json(OUT/"inventory.json", inv)
    def csv_counts(path, header, data):
        with path.open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f);w.writerow(header);w.writerows(data)
    csv_counts(OUT/"forge_tokens.csv",["kind","token","count"],[("forge_action",k,v) for k,v in forge_counts.most_common()]+[("forge_field",k,v) for k,v in field_counts.most_common()])
    # XMage classes are grouped heuristically by name suffix, while all class names remain visible.
    csv_counts(OUT/"xmage_classes.csv",["category","class_name","count"],[(class_category(k),k,v) for k,v in xmage_counts.most_common()])
    write_jsonl(OUT/"matched_cards.jsonl",matched);write_jsonl(OUT/"unmatched_forge.jsonl",unmatched_f);write_jsonl(OUT/"unmatched_xmage.jsonl",unmatched_x);write_jsonl(OUT/"ambiguous_matches.jsonl",ambiguous);write_jsonl(OUT/"requirement_candidates.jsonl",candidates)
    stats={"scryfall":len(sf),"forge":len(forge),"xmage":len(xmage),"forge_matched_records":sum(map(len,f_matches.values())),"xmage_matched_records":sum(map(len,x_matches.values())),"forge_cards":len(f_matches),"xmage_cards":len(x_matches),"both_cards":len(set(f_matches)&set(x_matches)),"unmatched_forge":len(unmatched_f),"unmatched_xmage":len(unmatched_x),"ambiguous":len(ambiguous),"oracle_text_comparison":{source:dict(counts) for source,counts in text_audit.items()},"requirements":dict(req_counts)}
    write_json(OUT/"stats.json",stats)
    return stats


def class_category(name):
    if name.startswith("Target"): return "Target"
    if name.startswith("Filter"): return "Filter"
    for suffix, cat in [("ReplacementEffect","ReplacementEffect"),("Ability","Ability"),("Effect","Effect"),("Cost","Cost"),("Target","Target"),("Filter","Filter"),("Condition","Condition")]:
        if name.endswith(suffix): return cat
    return "class_or_other"


def revisions():
    os.environ.setdefault("HF_HOME", str(RAW / "hf-home"))
    from huggingface_hub import HfApi
    api=HfApi(); result={}
    for key,repo in SOURCES.items():
        try: result[key]=api.dataset_info(repo).sha
        except Exception as e: result[key]=None
    return result


def report(stats=None):
    inv=json.loads((OUT/"inventory.json").read_text(encoding="utf-8")); stats=stats or json.loads((OUT/"stats.json").read_text(encoding="utf-8"))
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    lines=["# Manafold CAP miner: bootstrap experiment", "",f"Generated: {now} UTC", "", "## Dataset inventory", ""]
    for key,d in inv["datasets"].items(): lines += [f"### {key}: `{d['repository']}`", "",f"Revision: `{d.get('revision') or 'unavailable'}`. Rows: **{d['rows']:,}**. Splits: `{d['splits']}`.","",f"Columns: {', '.join('`'+c+'`' for c in d['columns'])}",""]
    import importlib.metadata as md
    versions={p:md.version(p) for p in ("datasets","huggingface_hub","PyYAML")}
    lines += [f"Dataset loading used `datasets`; repository revisions were queried with `huggingface_hub`. Local package versions: `{versions}`. Inventory generation/cache retrieval timestamp: `{inv['generated_at_utc']}` UTC. Rows were materialized from Hugging Face cache at `data/raw/hf`.","", "## Matching", "",f"Scryfall Oracle rows: {stats['scryfall']:,}; Forge records: {stats['forge']:,}; XMage records: {stats['xmage']:,}.",f"Forge records matched: {stats['forge_matched_records']:,}; distinct Oracle identities with Forge: {stats['forge_cards']:,} ({pct(stats['forge_cards'],stats['scryfall'])}).",f"XMage records matched: {stats['xmage_matched_records']:,}; distinct Oracle identities with XMage: {stats['xmage_cards']:,} ({pct(stats['xmage_cards'],stats['scryfall'])}).",f"Both: {stats['both_cards']:,} ({pct(stats['both_cards'],stats['scryfall'])}); unmatched Forge: {stats['unmatched_forge']:,}; unmatched XMage: {stats['unmatched_xmage']:,}; ambiguous records: {stats['ambiguous']:,}.",f"Normalized Oracle-text comparison after name matching: `{stats['oracle_text_comparison']}`. `MISMATCH` is diagnostic (it can indicate stale text, templating differences, or a bad match), not a silently rejected join.","", "Matching tries Oracle ID, normalized exact name (including face names), then normalized name plus normalized Oracle text. It does not fuzzy-match. Records with multiple exact-name candidates are retained as ambiguous.","", "## Forge vocabulary", "", "Action frequencies are in `data/output/forge_tokens.csv`; `$` field vocabulary is in `inventory.json`. The parser inventories observed action names rather than constraining them to a closed list. Top actions:",""]
    lines += table_rows(OUT/"forge_tokens.csv", 40, "forge_action")
    lines += ["", "Top Forge `$` fields:", ""]
    lines += table_rows(OUT/"forge_tokens.csv", 40, "forge_field")
    lines += ["", "## XMage vocabulary", "", "Java imports and class-like vocabulary are extracted lexically, not parsed as Java. Top classes:",""]
    lines += table_rows(OUT/"xmage_classes.csv",40)
    lines += ["", "## Cross-engine evidence", "",f"Requirement candidate counts by implementation evidence: `{stats['requirements']}`. `MULTI_IMPLEMENTATION_AGREEMENT` means both implementations have extracted constructs that the seed map assigns to the same generic candidate. It is corroboration only: all candidates remain `rules_evidence: NOT_CHECKED` and `review_status: UNREVIEWED`. `CONFLICT` is not inferred from different mapped effects on one card because cards commonly contain multiple effects, and this pass has no rule-aware contradiction detector.","", "## Examples and data quality", "", "Machine-readable records retain Oracle text, Forge input/action snippets, and XMage prompt/import/constructor excerpts needed to audit extraction. The report includes review samples below. Scryfall has one row per Oracle ID in this revision. Forge and XMage examples are generated implementation data; mismatched or stale text is possible. Face-name joins can associate a face with its parent card identity. No malformed records were silently repaired.","", "### Simple successful examples", ""]
    matched_rows=[json.loads(line) for line in (OUT/"matched_cards.jsonl").open(encoding="utf-8")]
    simple=[r for r in matched_rows if r["forge"]["present"] and r["xmage"]["present"] and len(r.get("oracle_text") or "")<120]
    lines += [f"- `{r['name']}` — Oracle: {(r.get('oracle_text') or '')[:140]} Forge: `{', '.join(r['forge']['actions'][:5])}`; XMage: `{', '.join(r['xmage']['classes'][:5])}`. Raw Forge: `{first_forge_excerpt(r)}`. Raw XMage: `{first_xmage_excerpt(r)}`." for r in simple[:10]]
    lines += ["", "### Interesting complex examples", ""]
    complex_rows=sorted((r for r in matched_rows if r["forge"]["present"] and r["xmage"]["present"]),key=lambda r:len(r.get("oracle_text") or ""),reverse=True)
    lines += [f"- `{r['name']}` — Oracle excerpt: {(r.get('oracle_text') or '')[:180]} Forge: `{', '.join(r['forge']['actions'][:8])}`; XMage: `{', '.join(r['xmage']['classes'][:8])}`. Raw Forge: `{first_forge_excerpt(r)}`. Raw XMage: `{first_xmage_excerpt(r)}`." for r in complex_rows[:10]]
    lines += ["", "### Unresolved examples", ""]
    candidate_rows=[json.loads(line) for line in (OUT/"requirement_candidates.jsonl").open(encoding="utf-8")]
    lines += [f"- `{r['name']}` — unmapped evidence retained: `{', '.join(dict.fromkeys(e['token'] for q in r['requirements'] for e in q['evidence']) )[:180]}`." for r in [c for c in candidate_rows if any(q['extraction_status']=='UNRESOLVED' for q in c['requirements'])][:10]]
    lines += ["", "### Ambiguous or problematic joins", ""]
    ambiguous_rows=[json.loads(line) for line in (OUT/"ambiguous_matches.jsonl").open(encoding="utf-8")]
    lines += [f"- `{card_name(r.get('record',{})) or '(name unavailable)'}` — `{r['source']}`: `{r['method']}`." for r in ambiguous_rows[:10]]
    lines += ["", "Observed matching issues include exact-name ambiguity and a small set of records with no exact Scryfall join. The current reports preserve those records in `ambiguous_matches.jsonl` and the source-specific unmatched files. Text mismatch is common: see measured comparisons above. Differences can be stale Oracle wording, templating, or a genuinely problematic join; this pass keeps the join and flags the difference rather than repairing it. The experiment does not systematically validate encoding or Java completeness.","", "## Assessment", "",f"1. Forge and XMage can bootstrap an evidence census over {pct(stats['both_cards'],stats['scryfall'])} of this Oracle corpus; the output remains implementation evidence, not a semantic census without review.",f"2. Forge evidence coverage: {pct(stats['forge_cards'],stats['scryfall'])}.",f"3. XMage evidence coverage: {pct(stats['xmage_cards'],stats['scryfall'])}.",f"4. Both: {pct(stats['both_cards'],stats['scryfall'])}.","5. Repeated actions/classes support a small reviewed mapping seed; the CSV frequency tables give the actual distribution.",f"6. Exact-name ambiguity affects {stats['ambiguous']:,} records; normalized Oracle-text mismatch occurs for Forge {stats['oracle_text_comparison']['forge'].get('MISMATCH',0):,} and XMage {stats['oracle_text_comparison']['xmage'].get('MISMATCH',0):,} matched records. Multiface names, absent fields, text currency, and non-card training examples need review.","7. Deterministic extraction is sufficient to create auditable candidates; it cannot establish correctness by agreement alone.","8. Small Phase 2: version-bound, risk-stratified human samples by pattern; blind double review for high-risk patterns; Wilson lower confidence bounds for precision; report reviewer agreement (simple agreement plus Cohen's kappa and Gwet's AC1 when useful); retain reviewer disagreement separately from extractor errors; stale validation when source, extractor, or mapping versions change; then make CAP eligibility an explicit versioned policy decision with a rule ID and reason. This repository does not yet implement that review or policy layer.","", "Authority boundary: Oracle text is card-specific input; this experiment does not retrieve Comprehensive Rules or official rulings. Forge and XMage are corroborating implementation witnesses only. No LLM, embeddings, or external classification service is used.",""]
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


def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=["download","inspect","mine","report","all"]);args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);RAW.mkdir(parents=True,exist_ok=True)
    if args.command in {"download","inspect","mine","all"}:
        loaded=load_sources(); rows=dataset_rows(loaded); rev=revisions();mine.revisions=rev
        if args.command in {"download","inspect"}:
            write_json(OUT/"inventory.json",inventory(rows,rev))
        if args.command in {"mine","all"}: stats=mine(rows)
        else: stats=None
    else: stats=None
    if args.command in {"report","all"}: report(stats)
    print(f"Completed {args.command}. Outputs: {OUT}")

if __name__ == "__main__": main()
