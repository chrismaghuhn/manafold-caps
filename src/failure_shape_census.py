"""Phase 0.2C analysis-only census of two reviewed extractor failure shapes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from src import cap_miner as miner

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output"
FORGE_FAILURE_IDS = {
    "053d9fe47d105986611506c8",
    "80e88eda5a088379b9af218a",
    "23a6562a6e6a5c5879b55310",
    "532892f8dc083b10a99ec57d",
}
XMAGE_FAILURE_ID = "xmage.destroy_target_effect.v1"
ZONES = {"library", "graveyard", "exile", "hand", "battlefield", "command", "stack", "ante"}


def _row_identity(source, index):
    return miner.reviewable_record_identity(source, miner.PINNED_REVISIONS[source], index)


def _clean_forge_value(value):
    return value.strip().strip('"').strip()


def forge_zone_occurrences(record, source_identity, card=None, forge_mapping=None):
    """Parse ChangeZone action lines independently, without altering miner output."""
    text = str(record.get("output", "")).replace("\\n", "\n")
    forge_mapping = forge_mapping if forge_mapping is not None else yaml_mapping().get("forge", {})
    result = []
    action_re = re.compile(r"(?:^|[\n\r|:])\s*(?:(?:A:)?(?:AB|SP|DB)\$|[TS]:Mode\$)\s*([^|\r\n]+)([^\r\n]*)")
    for match in action_re.finditer(text):
        action = match.group(1).strip()
        if action not in {"ChangeZone", "ChangeZoneAll"}:
            continue
        line = match.group(0)
        fields = {}
        for key, raw in re.findall(r"\b([A-Za-z][\w]*)\$\s*([^|\r\n]+)", line):
            fields.setdefault(key, []).append(_clean_forge_value(raw))
        origins = fields.get("Origin", [])
        destinations = fields.get("Destination", [])
        origin_values = [x.strip() for x in re.split(r"\s*,\s*", origins[0])] if len(origins) == 1 else origins
        destination_values = [x.strip() for x in re.split(r"\s*,\s*", destinations[0])] if len(destinations) == 1 else destinations
        origin_values = [x for x in origin_values if x]
        destination_values = [x for x in destination_values if x]
        if not origins:
            classification = "ORIGIN_MISSING"
        elif not destinations:
            classification = "DESTINATION_MISSING"
        elif len(origin_values) != 1 or len(destination_values) != 1 or origin_values[0].casefold() == "any" or destination_values[0].casefold() == "any":
            classification = "ORIGIN_OR_DESTINATION_MULTI_VALUED"
        elif origin_values[0].casefold() not in ZONES or destination_values[0].casefold() not in ZONES:
            classification = "OTHER_UNRESOLVED"
        elif origin_values[0].casefold() == destination_values[0].casefold():
            classification = "SAME_ZONE"
        else:
            classification = "CROSS_ZONE"
        result.append({
            "source": "forge", "source_record_identity": source_identity,
            "action_type": action, "classification": classification,
            "origin": origins, "destination": destinations,
            "parameters": {k: v for k, v in fields.items() if k not in {"Origin", "Destination"}},
            "card_name": (card or {}).get("name") or miner.card_name(record) or None,
            "oracle_id": (card or {}).get("oracle_id"),
            "currently_mapped_requirement": forge_mapping.get(action),
            "raw_action_snippet": line.strip(),
        })
    return result


def yaml_mapping():
    return yaml.safe_load((ROOT / "mappings.yaml").read_text(encoding="utf-8"))


def strip_java_non_code(source, include_contexts=False):
    """Mask Java comments and literals; optionally return their separate masks."""
    chars = list(source)
    comment_chars = ["\n" if ch == "\n" else "\r" if ch == "\r" else " " for ch in source]
    literal_chars = comment_chars.copy()
    i = 0
    state = "code"
    while i < len(chars):
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                comment_chars[i] = comment_chars[i + 1] = "/"
                chars[i] = chars[i + 1] = " "
                i += 2; state = "line_comment"; continue
            if ch == "/" and nxt == "*":
                comment_chars[i] = comment_chars[i + 1] = "/"
                chars[i] = chars[i + 1] = " "
                i += 2; state = "block_comment"; continue
            if ch == '"':
                literal_chars[i] = '"'
                chars[i] = " "; state = "string"; i += 1; continue
            if ch == "'":
                literal_chars[i] = "'"
                chars[i] = " "; state = "char"; i += 1; continue
        elif state in {"line_comment", "block_comment", "string", "char"}:
            if state in {"line_comment", "block_comment"}:
                comment_chars[i] = ch
            else:
                literal_chars[i] = ch
            if ch not in "\r\n": chars[i] = " "
            if state == "line_comment" and ch in "\r\n": state = "code"
            elif state == "block_comment" and ch == "*" and nxt == "/":
                chars[i + 1] = " "; i += 1; state = "code"
            elif state in {"string", "char"}:
                if ch == "\\" and i + 1 < len(chars):
                    if chars[i + 1] not in "\r\n": chars[i + 1] = " "
                    i += 1
                elif (state == "string" and ch == '"') or (state == "char" and ch == "'"):
                    state = "code"
        i += 1
    code = "".join(chars)
    if include_contexts:
        return code, "".join(comment_chars), "".join(literal_chars)
    return code


def classify_java_class_usage(source, class_name, non_code=None, imports=None, comment_mask=None, literal_mask=None):
    imports = imports if imports is not None else re.findall(r"(?m)^\s*import\s+(?:static\s+)?([\w.*]+)\s*;", source)
    imported = any(path.rsplit(".", 1)[-1] == class_name for path in imports)
    package_lines = re.findall(r"(?m)^\s*package\s+[^;]*\b" + re.escape(class_name) + r"\b[^;]*;", source)
    if non_code is None or comment_mask is None or literal_mask is None:
        generated_code, generated_comments, generated_literals = strip_java_non_code(source, include_contexts=True)
        non_code = non_code if non_code is not None else generated_code
        comment_mask = comment_mask if comment_mask is not None else generated_comments
        literal_mask = literal_mask if literal_mask is not None else generated_literals
    # Remove import/package declarations from executable context.
    executable = re.sub(r"(?m)^\s*(?:import\s+(?:static\s+)?[^;]+;|package\s+[^;]+;)", "", non_code)
    escaped = re.escape(class_name)
    instantiated = bool(re.search(r"\bnew\s+(?:[\w$]+\.)*" + escaped + r"\s*\(", executable))
    executable_mentions = list(re.finditer(r"\b" + escaped + r"\b", executable))
    if instantiated:
        classification = "INSTANTIATED"
    elif executable_mentions:
        classification = "USED_OTHER_EXECUTABLE_CONTEXT"
    elif imported:
        classification = "IMPORTED_ONLY"
    else:
        classification = "UNRESOLVED_USAGE"
    comment_mentions = len(re.findall(r"\b" + escaped + r"\b", comment_mask or ""))
    string_mentions = len(re.findall(r"\b" + escaped + r"\b", literal_mask or ""))
    comment_string_mentions = comment_mentions + string_mentions
    return {
        "classification": classification,
        "imported": imported,
        "import_paths": [p for p in imports if p.rsplit(".", 1)[-1] == class_name],
        "instantiated": instantiated,
        "executable_mentions": len(executable_mentions),
        "comment_or_string_mentions": max(0, comment_string_mentions),
        "comment_mentions": comment_mentions,
        "string_literal_mentions": string_mentions,
        "package_mentions": len(package_lines),
        "comment_or_string_only": not executable_mentions and not imported and comment_string_mentions > 0,
    }


# Keep the census and production guard on the same lexical usage implementation.
strip_java_non_code = miner.strip_java_non_code
classify_java_class_usage = miner.classify_java_class_usage


def _read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)


def _exact_source_matcher(scryfall_cards):
    """Mirror the miner's deterministic identity layers for audit attribution."""
    by_id, by_name = defaultdict(list), defaultdict(list)
    for index, card in enumerate(scryfall_cards):
        if card.get("oracle_id"): by_id[str(card["oracle_id"])].append(index)
        name = miner.norm(card.get("name"))
        if name: by_name[name].append(index)
        for face in card.get("card_faces") or []:
            face_name = miner.norm(face.get("name")) if isinstance(face, dict) else ""
            if face_name: by_name[face_name].append(index)

    def match(record):
        oracle_id = record.get("oracle_id") or record.get("oracleId")
        if oracle_id and len(by_id.get(str(oracle_id), [])) == 1:
            return by_id[str(oracle_id)][0], "oracle_id"
        name = miner.norm(miner.card_name(record))
        if not name: return None, "unmatched"
        candidates = list(dict.fromkeys(by_name.get(name, [])))
        if len(candidates) == 1: return candidates[0], "normalized_name"
        if len(candidates) > 1:
            text = miner.norm(miner.oracle_text(record))
            exact = [i for i in candidates if text and text in miner.scryfall_text_options(scryfall_cards[i])]
            return (exact[0], "normalized_name_and_oracle_text") if len(exact) == 1 else (None, "ambiguous")
        return None, "unmatched"
    return match


def _sample_guard_impact(samples, final_labels, affected_occurrences, engine):
    affected = []
    for sample in samples:
        pattern = sample.get("pattern", {})
        constructs = []
        if pattern.get("source") == engine and pattern.get("external_construct"):
            constructs.append(pattern["external_construct"])
        for construct in pattern.get("external_constructs") or []:
            if construct.get("source") == engine:
                constructs.append(construct.get("token") or construct.get("class"))
        evidence = sample.get("evidence", {}).get(engine, {})
        source_id = evidence.get("source_record_identity")
        if any((engine, source_id, construct) in affected_occurrences for construct in constructs):
            affected.append({"sample_id": sample["sample_id"], "pattern_id": sample["pattern_id"], "label": final_labels.get(sample["sample_id"]), "card_name": sample["card"]["name"]})
    counts = Counter(item["label"] for item in affected)
    return {"samples_changed": len(affected), "CORRECT": counts["CORRECT"], "WRONG": counts["WRONG"], "affected_samples": affected}


def _review_labels(reviewer_a_path, reviewer_b_path):
    a = yaml.safe_load(Path(reviewer_a_path).read_text(encoding="utf-8"))["decisions"]
    b = yaml.safe_load(Path(reviewer_b_path).read_text(encoding="utf-8"))["decisions"]
    a_ids = {r["sample_id"] for r in a}
    b_ids = {r["sample_id"] for r in b}
    if len(a) != 460 or len(a_ids) != 460 or len(b) != 208 or len(b_ids) != 208 or not b_ids <= a_ids:
        raise ValueError("Expected 460 unique Reviewer-A IDs and 208 unique Reviewer-B IDs as an exact A subset")
    decisions = {r["sample_id"]: r["decision"] for r in a}
    adjudications = yaml.safe_load((ROOT / "adjudication_results.yaml").read_text(encoding="utf-8"))["decisions"]
    decisions.update({r["sample_id"]: r["final_label"] for r in adjudications})
    counts = Counter(decisions.values())
    if len(decisions) != 460 or counts != Counter({"CORRECT": 455, "WRONG": 5}):
        raise ValueError(f"Unexpected final Phase 0.2B primary labels: {dict(counts)}")
    return decisions


def run_census(reviewer_a_path, reviewer_b_path):
    mapping = yaml_mapping()
    mapping_sha = hashlib.sha256((ROOT / "mappings.yaml").read_bytes()).hexdigest()
    if mapping_sha != "3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a":
        raise ValueError(f"Mapping SHA changed from the Phase 0.2B validation scope: {mapping_sha}")
    if miner.EXTRACTOR_VERSION != "0.2.0":
        raise ValueError(f"Expected extractor 0.2.0, got {miner.EXTRACTOR_VERSION}")
    pinned = dict(miner.PINNED_REVISIONS)
    validation = yaml.safe_load((ROOT / "validation_results.yaml").read_text(encoding="utf-8"))
    if validation["validation_scope"]["source_set"] != pinned or validation["validation_scope"]["mapping_sha256"] != mapping_sha:
        raise ValueError("Phase 0.2B validation scope does not match the pinned census inputs")

    loaded = miner.dataset_rows(miner.load_sources())
    forge = [r for split in loaded["forge"].values() for r in split]
    xmage = [r for split in loaded["xmage"].values() for r in split]
    scryfall = [r for split in loaded["scryfall"].values() for r in split]
    match_source = _exact_source_matcher(scryfall)

    forge_rows = []
    forge_zone_all = []
    for index, record in enumerate(forge):
        rid = _row_identity("forge", index)
        card_index, match_method = match_source(record)
        card = scryfall[card_index] if card_index is not None else None
        for occurrence in forge_zone_occurrences(record, rid, card, mapping.get("forge", {})):
            occurrence["match_method"] = match_method
            forge_zone_all.append(occurrence)
            if occurrence["classification"] == "SAME_ZONE": forge_rows.append(occurrence)

    forge_review = yaml.safe_load((ROOT / "adjudication_results.yaml").read_text(encoding="utf-8"))["decisions"]
    samples = list(_read_jsonl(OUT / "review_samples.jsonl"))
    final_labels = _review_labels(reviewer_a_path, reviewer_b_path)
    sample_by_id = {row["sample_id"]: row for row in samples if row.get("selection_basis") == "PROBABILITY_SAMPLE"}
    forge_failure_occurrences = {}
    for decision in forge_review:
        sample = sample_by_id[decision["sample_id"]]
        rid = sample["evidence"]["forge"]["source_record_identity"]
        forge_failure_occurrences[decision["sample_id"]] = [x for x in forge_zone_all if x["source_record_identity"] == rid and x["classification"] == "SAME_ZONE"]
    if set(forge_failure_occurrences) != FORGE_FAILURE_IDS or any(not occurrences for occurrences in forge_failure_occurrences.values()):
        missing = sorted(sid for sid, occurrences in forge_failure_occurrences.items() if not occurrences)
        raise ValueError(f"Could not trace all four adjudicated Forge failures into SAME_ZONE census: {missing}")

    forge_by_pair = Counter((r["action_type"], r["origin"][0], r["destination"][0]) for r in forge_rows)
    forge_action_counts = Counter(r["action_type"] for r in forge_zone_all)
    forge_row_action_states = defaultdict(set)
    for row in forge_zone_all:
        forge_row_action_states[(row["source_record_identity"], row["action_type"])].add(row["classification"])
    forge_affected_occurrences = {("forge", rid, action) for (rid, action), states in forge_row_action_states.items() if "SAME_ZONE" in states and not (states - {"SAME_ZONE"})}
    forge_sample_impact = _sample_guard_impact(samples, final_labels, forge_affected_occurrences, "forge")

    mapped_xmage = mapping.get("xmage", {})
    xmage_rows = []
    for index, record in enumerate(xmage):
        rid = _row_identity("xmage", index)
        card_index, match_method = match_source(record)
        card = scryfall[card_index] if card_index is not None else {}
        java = record.get("completion", record.get("output", ""))
        java = java if isinstance(java, str) else "\n".join(miner.flatten_text(java))
        masked_java, comment_mask, literal_mask = strip_java_non_code(java, include_contexts=True)
        imports = re.findall(r"(?m)^\s*import\s+(?:static\s+)?([\w.*]+)\s*;", java)
        _, extracted_classes, _ = miner.java_extract(java)
        extracted = set(miner.xmage_semantic_classes(extracted_classes))
        for class_name, requirement in sorted(mapped_xmage.items()):
            # Include classes actually seen by extractor 0.2.0 and explicit
            # non-code-only appearances for diagnostic coverage.
            usage = classify_java_class_usage(java, class_name, masked_java, imports, comment_mask, literal_mask)
            raw_mentions = len(re.findall(r"\b" + re.escape(class_name) + r"\b", java))
            if class_name not in extracted and not raw_mentions:
                continue
            xmage_rows.append({
                "source": "xmage", "source_record_identity": rid,
                "card_name": card.get("name") or miner.card_name(record) or None,
                "oracle_id": card.get("oracle_id"), "mapped_class": class_name,
                "match_method": match_method,
                "mapped_requirement": requirement,
                "extracted_by_v0_2_0": class_name in extracted,
                "source_class_occurrence_count": raw_mentions,
                **usage,
            })
    xmage_candidate_rows = [r for r in xmage_rows if r["extracted_by_v0_2_0"] and r["oracle_id"]]
    xmage_candidate_import_only = [r for r in xmage_candidate_rows if r["classification"] in {"IMPORTED_ONLY", "UNRESOLVED_USAGE"} and not r["executable_mentions"]]
    xmage_affected_occurrences = {("xmage", r["source_record_identity"], r["mapped_class"]) for r in xmage_candidate_import_only}
    xmage_sample_impact = _sample_guard_impact(samples, final_labels, xmage_affected_occurrences, "xmage")

    known_xmage_samples = [s for s in samples if s["pattern_id"] == XMAGE_FAILURE_ID and final_labels.get(s["sample_id"]) == "WRONG"]
    xmage_known_captured = any(("xmage", s["evidence"]["xmage"]["source_record_identity"], "DestroyTargetEffect") in xmage_affected_occurrences for s in known_xmage_samples)
    if len(known_xmage_samples) != 1 or not xmage_known_captured:
        known_ids = [s["evidence"]["xmage"].get("source_record_identity") for s in known_xmage_samples]
        matched_rows = [r for r in xmage_rows if r["source_record_identity"] in known_ids and r["mapped_class"] == "DestroyTargetEffect"]
        raise ValueError(f"Could not reproduce the known XMage imported-only false positive: sample_n={len(known_xmage_samples)}, source_ids={known_ids}, census_rows={matched_rows}")

    # Occurrence-level populations include all extracted mapped Forge actions
    # and all mapped-class occurrences exposed by extractor 0.2.0.
    forge_action_population = [r for r in forge_zone_all if r["classification"] in {"SAME_ZONE", "CROSS_ZONE", "ORIGIN_MISSING", "DESTINATION_MISSING", "ORIGIN_OR_DESTINATION_MULTI_VALUED", "OTHER_UNRESOLVED"}]
    forge_mapped_same = [r for r in forge_rows if r["oracle_id"] and r["currently_mapped_requirement"] == "zone_transition"]
    forge_same_oracle = {r["oracle_id"] for r in forge_mapped_same}
    forge_same_cards = {r["oracle_id"] for r in forge_mapped_same if r["oracle_id"]}
    xmage_covered_classes = set(mapped_xmage)
    xmage_mappings_with_import_only = sorted({r["mapped_class"] for r in xmage_candidate_import_only})
    xmage_import_only_oracles = {r["oracle_id"] for r in xmage_candidate_import_only if r["oracle_id"]}
    xmage_import_only_cards = {r["oracle_id"] for r in xmage_candidate_import_only if r["oracle_id"]}

    # A mapped candidate occurrence is keyed by source-record plus token/class.
    forge_affected_occurrences = [r for r in forge_rows if r["oracle_id"]]
    xmage_affected_occurrences = xmage_candidate_import_only
    combined_occurrence_keys = {("forge", r["source_record_identity"], r["action_type"], i) for i, r in enumerate(forge_affected_occurrences)} | {("xmage", r["source_record_identity"], r["mapped_class"]) for r in xmage_affected_occurrences}
    combined_cards = forge_same_cards | xmage_import_only_cards
    combined_oracles = forge_same_oracle | xmage_import_only_oracles
    requirements = {"zone_transition"} if forge_affected_occurrences else set()
    requirements.update(r["mapped_requirement"] for r in xmage_affected_occurrences)
    validation_plan = yaml.safe_load((ROOT / "validation_plan.yaml").read_text(encoding="utf-8"))
    affected_paths = {
        "forge": {r["action_type"] for r in forge_affected_occurrences},
        "xmage": {r["mapped_class"] for r in xmage_affected_occurrences},
    }
    validation_patterns_affected = []
    forge_validation_patterns = []
    xmage_validation_patterns = []
    for spec in validation_plan["patterns"]:
        specs = spec.get("external_constructs") or [{"source": spec.get("source"), "token": spec.get("external_construct")}]
        if any(path.get("source") in affected_paths and (path.get("token") or path.get("class")) in affected_paths[path.get("source")] for path in specs):
            validation_patterns_affected.append(spec["pattern_id"])
            if any(path.get("source") == "forge" and (path.get("token") or path.get("class")) in affected_paths["forge"] for path in specs):
                forge_validation_patterns.append(spec["pattern_id"])
            if any(path.get("source") == "xmage" and (path.get("token") or path.get("class")) in affected_paths["xmage"] for path in specs):
                xmage_validation_patterns.append(spec["pattern_id"])
    affected_mapping_paths = sorted(
        {f"forge:{action} -> zone_transition" for action in affected_paths["forge"]}
        | {f"xmage:{row['mapped_class']} -> {row['mapped_requirement']}" for row in xmage_affected_occurrences}
    )

    forge_category_counts = Counter()
    for row in forge_rows:
        params = row["parameters"]
        if row["parameters"].get("RandomOrder") == ["True"]: category = "RANDOM_ORDER_REINSERTION"
        elif row["parameters"].get("LibraryPosition") == ["-1"]: category = "BOTTOM_OF_LIBRARY_REPOSITIONING"
        elif row["parameters"].get("LibraryPosition") == ["0"]: category = "TOP_OF_LIBRARY_REPOSITIONING"
        elif row["parameters"].get("RememberChanged") or row["parameters"].get("ChangeType", [""])[0].find("Remembered") >= 0: category = "REMEMBERED_CARD_CLEANUP"
        elif "search" in row["raw_action_snippet"].casefold() or "reveal" in row["raw_action_snippet"].casefold(): category = "LIBRARY_SEARCH_OR_REVEAL_STAGING"
        else: category = "UNCLASSIFIED"
        forge_category_counts[category] += 1

    forge_by_action = Counter(r["action_type"] for r in forge_rows)
    forge_by_action_all = Counter(r["action_type"] for r in forge_action_population)
    forge_non_zone_extracted = Counter()
    for record in forge:
        actions, _, _ = miner.forge_extract(record.get("output", miner.all_strings(record)))
        forge_non_zone_extracted.update(a for a in actions if a in {"ChangeZone", "ChangeZoneAll"})
    if sum(forge_by_action_all.values()) != sum(forge_non_zone_extracted.values()):
        # Invalid/missing cases are still expected to be present in the parser
        # output. The guard is intentional: silently partial census is not useful.
        raise ValueError("Per-occurrence Forge parser population disagrees with Forge 0.2.0 action-token census")

    category_order = sorted(forge_by_pair.items(), key=lambda item: (-item[1], item[0]))
    forge_summary = {
        "source_records_scanned": len(forge),
        "action_occurrences": dict(sorted(forge_action_counts.items())),
        "same_zone_occurrences_total": len(forge_rows),
        "same_zone_occurrences_mapped_to_zone_transition": len(forge_mapped_same),
        "distinct_cards_affected": len(forge_same_cards), "distinct_oracle_ids_affected": len(forge_same_oracle),
        "same_zone_by_action": dict(sorted(forge_by_action.items())),
        "same_zone_pairs": [{"action_type": action, "origin": origin, "destination": destination, "count": count} for (action, origin, destination), count in category_order],
        "same_zone_semantic_subgroups": dict(sorted(forge_category_counts.items())),
        "classification_counts": dict(sorted(Counter(r["classification"] for r in forge_zone_all).items())),
        "all_extracted_action_counts": dict(sorted(forge_non_zone_extracted.items())),
        "reviewed_failure_membership": {sid: {"captured": bool(occurrences), "source_record_identity": sample_by_id[sid]["evidence"]["forge"]["source_record_identity"], "card_name": sample_by_id[sid]["card"]["name"]} for sid, occurrences in sorted(forge_failure_occurrences.items())},
        "hypothetical_guard_impact": {"candidate_occurrences_removed": len(forge_mapped_same), "distinct_cards_changed": len(forge_same_cards), "distinct_oracle_ids_changed": len(forge_same_oracle), "patterns_affected": sorted(forge_validation_patterns)},
        "reviewed_sample_impact": forge_sample_impact,
    }
    classes_summary = {}
    for class_name, requirement in sorted(mapped_xmage.items()):
        all_records = [r for r in xmage_rows if r["mapped_class"] == class_name]
        extracted_records = [r for r in all_records if r["extracted_by_v0_2_0"]]
        imported_only = [r for r in extracted_records if r["classification"] == "IMPORTED_ONLY"]
        classes_summary[class_name] = {
            "mapped_requirement": requirement, "source_records_mentioning_class": len(all_records),
            "extracted_by_v0_2_0_records": len(extracted_records),
            "IMPORTED_ONLY": len(imported_only),
            "INSTANTIATED": sum(r["classification"] == "INSTANTIATED" for r in extracted_records),
            "USED_OTHER_EXECUTABLE_CONTEXT": sum(r["classification"] == "USED_OTHER_EXECUTABLE_CONTEXT" for r in extracted_records),
            "UNRESOLVED_USAGE": sum(r["classification"] == "UNRESOLVED_USAGE" for r in extracted_records),
            "distinct_cards_affected_by_import_only": len({r["card_name"] for r in imported_only if r["card_name"]}),
            "distinct_oracle_ids_affected_by_import_only": len({r["oracle_id"] for r in imported_only if r["oracle_id"]}),
        }
    xmage_summary = {
        "source_records_scanned": len(xmage),
        "mapped_classes_scanned": len(xmage_covered_classes), "classes": classes_summary,
        "dataset_imported_only_occurrences": sum(row["IMPORTED_ONLY"] for row in classes_summary.values()),
        "imported_only_occurrences": len(xmage_candidate_import_only),
        "imported_only_distinct_cards": len(xmage_import_only_cards),
        "imported_only_distinct_oracle_ids": len(xmage_import_only_oracles),
        "mappings_with_import_only_cases": xmage_mappings_with_import_only,
        "hypothetical_guard_impact": {"occurrences_removed": len(xmage_candidate_import_only), "distinct_cards_changed": len(xmage_import_only_cards), "distinct_oracle_ids_changed": len(xmage_import_only_oracles), "mapping_paths_affected": sorted({f"xmage:{r['mapped_class']} -> {r['mapped_requirement']}" for r in xmage_candidate_import_only}), "patterns_affected": sorted(xmage_validation_patterns)},
        "reviewed_sample_impact": xmage_sample_impact,
        "known_false_positive": [{"sample_id": s["sample_id"], "card_name": s["card"]["name"], "oracle_id": s["card"]["oracle_id"], "source_record_identity": s["evidence"]["xmage"]["source_record_identity"], "mapped_class": "DestroyTargetEffect", "classification": "IMPORTED_ONLY", "captured": xmage_known_captured} for s in known_xmage_samples],
        "non_executable_context_mentions": {"comment_occurrences": sum(r["comment_mentions"] for r in xmage_rows), "string_literal_occurrences": sum(r["string_literal_mentions"] for r in xmage_rows), "comment_or_string_only_records": sum(r["comment_or_string_only"] for r in xmage_rows), "import_only_records": sum(r["classification"] == "IMPORTED_ONLY" and r["extracted_by_v0_2_0"] for r in xmage_rows), "package_mentions": sum(r["package_mentions"] > 0 for r in xmage_rows)},
    }
    combined = {
        "mapped_occurrences_changed": len(combined_occurrence_keys),
        "distinct_cards_changed": len(combined_cards), "distinct_oracle_ids_changed": len(combined_oracles),
        "requirements_affected": sorted(requirements), "patterns_affected": sorted(validation_patterns_affected), "mapping_paths_affected": affected_mapping_paths,
        "reviewed_sample_impact": {"samples_changed_union": len({x["sample_id"] for x in forge_sample_impact["affected_samples"] + xmage_sample_impact["affected_samples"]}), "CORRECT": sum(x["label"] == "CORRECT" for x in forge_sample_impact["affected_samples"] + xmage_sample_impact["affected_samples"]), "WRONG": sum(x["label"] == "WRONG" for x in forge_sample_impact["affected_samples"] + xmage_sample_impact["affected_samples"]), "forge": forge_sample_impact, "xmage": xmage_sample_impact},
    }
    guard_design = {
        "guard_design_version": 1,
        "validation_scope": {"extractor_version": miner.EXTRACTOR_VERSION, "mapping_sha256": mapping_sha, "source_set": pinned},
        "review_input_provenance": {"reviewer_a_sha256": hashlib.sha256(Path(reviewer_a_path).read_bytes()).hexdigest(), "reviewer_b_sha256": hashlib.sha256(Path(reviewer_b_path).read_bytes()).hexdigest(), "adjudication_sha256": hashlib.sha256((ROOT / "adjudication_results.yaml").read_bytes()).hexdigest()},
        "forge_same_zone": {"status": "CANDIDATE" if forge_sample_impact["CORRECT"] == 0 else "UNSAFE", "observed_failure_shape": {"action_types": ["ChangeZone", "ChangeZoneAll"], "predicate": {"origin_equals_destination": True}}, "census": forge_summary, "hypothetical_impact": forge_summary["hypothetical_guard_impact"], "reviewed_sample_impact": forge_sample_impact, "implementation_recommendation": "Use only individual action occurrences whose origin and destination are singular recognized zones and equal. Keep multi-valued, missing, dynamic, or unrecognized endpoints unresolved; do not infer a pair from card-level parameter lists. Candidate status requires no reviewed CORRECT sample occurrence to be eliminated."},
        "xmage_import_only": {"status": "CANDIDATE", "observed_failure_shape": {"only_non_executable_reference": True}, "census": xmage_summary, "hypothetical_impact": xmage_summary["hypothetical_guard_impact"], "reviewed_sample_impact": xmage_sample_impact, "implementation_recommendation": "Use lexical Java masking for comments and string/char literals, remove import/package declarations, and require a constructor or executable code reference for mapped evidence. Keep unresolved lexical cases visible for review."},
        "combined_counterfactual": combined,
    }

    # Dataset audit output includes only explicit same-zone Forge action occurrences.
    forge_rows.sort(key=lambda r: (r["action_type"], r["origin"], r["destination"], r["source_record_identity"]))
    xmage_rows.sort(key=lambda r: (r["mapped_class"], r["source_record_identity"], r["classification"]))
    miner.write_jsonl(OUT / "forge_same_zone_occurrences.jsonl", forge_rows)
    miner.write_jsonl(OUT / "xmage_usage_census.jsonl", xmage_rows)
    (ROOT / "guard_design.yaml").write_text(yaml.safe_dump(guard_design, sort_keys=False, allow_unicode=True), encoding="utf-8")
    write_census_report(guard_design, reviewer_a_path, reviewer_b_path)
    return guard_design


def write_census_report(design, reviewer_a_path, reviewer_b_path):
    forge = design["forge_same_zone"]["census"]
    xmage = design["xmage_import_only"]["census"]
    combined = design["combined_counterfactual"]
    lines = [
        "# Phase 0.2C — Failure-Shape Census & Guard Design", "",
        "## Scope", "",
        f"Pinned revisions: Scryfall `{miner.PINNED_REVISIONS['scryfall']}`, Forge `{miner.PINNED_REVISIONS['forge']}`, XMage `{miner.PINNED_REVISIONS['xmage']}`. Extractor `{miner.EXTRACTOR_VERSION}`; mapping SHA-256 `{design['validation_scope']['mapping_sha256']}`.",
        "This is an analysis-only full-corpus census. The miner, mappings, sample IDs, and Phase 0.2B precision results are unchanged.", "",
        "## Phase 0.2B findings being investigated", "",
        "Phase 0.2B recorded four WRONG Forge samples involving same-library movement and one WRONG XMage sample where `DestroyTargetEffect` appeared as an import without executable use. These are extractor-candidate false positives; they do not by themselves invalidate the generic mappings.", "",
        "## Forge same-zone census", "",
        f"Scanned {forge['source_records_scanned']:,} pinned Forge source records. Parsed ChangeZone-family actions: `{forge['all_extracted_action_counts']}`. All parsed action occurrences were retained in the classification census; {forge['same_zone_occurrences_total']} are unambiguous SAME_ZONE occurrences, of which {forge['same_zone_occurrences_mapped_to_zone_transition']} join to a Scryfall identity and currently map to `zone_transition`.",
        f"Distinct affected cards: {forge['distinct_cards_affected']}; distinct Oracle IDs: {forge['distinct_oracle_ids_affected']}. Classification counts: `{forge['classification_counts']}`.", "",
        "| action | origin | destination | count |", "|---|---|---|---:|",
    ]
    lines += [f"| {r['action_type']} | {r['origin']} | {r['destination']} | {r['count']} |" for r in forge["same_zone_pairs"]]
    lines += ["", f"Descriptive same-zone subgroups (non-exclusive cues assigned by priority): `{forge['same_zone_semantic_subgroups']}`. These are not semantic conclusions; unresolved evidence remains `UNCLASSIFIED`.", "", "Reviewed failure traceability:", ""]
    lines += [f"- `{sid}` — {row['card_name']}: captured={row['captured']}, source `{row['source_record_identity']}`." for sid, row in forge["reviewed_failure_membership"].items()]
    lines += ["", "## Forge hypothetical guard impact", "", f"The counterfactual guard removes {forge['hypothetical_guard_impact']['candidate_occurrences_removed']} currently mapped SAME_ZONE action occurrences across {forge['hypothetical_guard_impact']['distinct_cards_changed']} cards / {forge['hypothetical_guard_impact']['distinct_oracle_ids_changed']} Oracle IDs. Patterns: `{forge['hypothetical_guard_impact']['patterns_affected']}`.", f"Among primary review samples: {forge['reviewed_sample_impact']['samples_changed']} changed; CORRECT={forge['reviewed_sample_impact']['CORRECT']}, WRONG={forge['reviewed_sample_impact']['WRONG']}. This counterfactual does not recalculate precision.", "", "## XMage mapped-class usage census", "", f"Scanned {xmage['source_records_scanned']:,} pinned XMage source records and all {xmage['mapped_classes_scanned']} mapped classes from `mappings.yaml`. Across joined candidate records, {xmage['imported_only_occurrences']} extracted class-record occurrences are imported only, affecting {xmage['imported_only_distinct_cards']} cards / {xmage['imported_only_distinct_oracle_ids']} Oracle IDs and {len(xmage['mappings_with_import_only_cases'])} mappings. The all-source imported-only count is {xmage['dataset_imported_only_occurrences']}.", "", "| mapped class | requirement | source records mentioning class | extracted records | imported only | instantiated | executable use | unresolved | cards affected |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for cls, row in xmage["classes"].items():
        lines.append(f"| `{cls}` | `{row['mapped_requirement']}` | {row['source_records_mentioning_class']} | {row['extracted_by_v0_2_0_records']} | {row['IMPORTED_ONLY']} | {row['INSTANTIATED']} | {row['USED_OTHER_EXECUTABLE_CONTEXT']} | {row['UNRESOLVED_USAGE']} | {row['distinct_cards_affected_by_import_only']} |")
    known = xmage["known_false_positive"][0]
    lines += ["", f"Known false positive reproduced: `{known['sample_id']}` / {known['card_name']} / `{known['mapped_class']}` = `{known['classification']}` (captured={known['captured']}); source `{known['source_record_identity']}`.", f"Non-executable context diagnostics: `{xmage['non_executable_context_mentions']}`. Comments, strings, imports, and package declarations are not treated as executable usage.", "", "## XMage hypothetical guard impact", "", f"The counterfactual guard removes {xmage['hypothetical_guard_impact']['occurrences_removed']} joined mapped class-record occurrences, affecting {xmage['hypothetical_guard_impact']['distinct_cards_changed']} cards / {xmage['hypothetical_guard_impact']['distinct_oracle_ids_changed']} Oracle IDs. Mapping paths affected: `{xmage['hypothetical_guard_impact']['mapping_paths_affected']}`. Selected validation patterns affected: `{xmage['hypothetical_guard_impact']['patterns_affected']}`.", f"Among primary review samples: {xmage['reviewed_sample_impact']['samples_changed']} changed; CORRECT={xmage['reviewed_sample_impact']['CORRECT']}, WRONG={xmage['reviewed_sample_impact']['WRONG']}.", "", "## Review-sample impact", "", "Labels use Phase 0.2B Reviewer-A outcomes with the four accepted adjudications applied. Forced audit is excluded. A sample is counted only when the guard removes its selected mapping construct from that source record; cross-engine examples are affected only on the corresponding evidence path. Both guards are counterfactual only.", "", "## Combined counterfactual impact", "", f"Union after occurrence/card/Oracle deduplication: {combined['mapped_occurrences_changed']} mapped occurrences, {combined['distinct_cards_changed']} distinct cards, {combined['distinct_oracle_ids_changed']} Oracle IDs; requirements `{combined['requirements_affected']}`; selected validation patterns `{combined['patterns_affected']}`; mapping paths `{combined['mapping_paths_affected']}`.", f"Reviewed sample union: {combined['reviewed_sample_impact']['samples_changed_union']} samples, CORRECT={combined['reviewed_sample_impact']['CORRECT']}, WRONG={combined['reviewed_sample_impact']['WRONG']}.", "", "## Guard design recommendation", "", f"Forge guard: `{design['forge_same_zone']['status']}`. XMage guard: `{design['xmage_import_only']['status']}`. Neither is approved or implemented. See `guard_design.yaml` for explicit predicates, counts, limitations, and recommendations.", "", "## Validation consequences", "", "The 0.2B estimates remain bound to extractor 0.2.0 and are historical. No adjusted precision, interval, or Requirement-level score was calculated. Any future guard implementation needs a new extractor version, a source-occurrence differential, and validation under a new scope.", "", "## Next phase", "", "A narrowly scoped guard implementation can be considered after reviewing this census. The evidence distinguishes mapping correctness from candidate extraction: genuine `DestroyTargetEffect` uses may still map to `destroy`; only import-only records should cease to count. Likewise, `ChangeZone` remains a useful zone-transition signal when endpoints differ; this census only identifies same-zone occurrences for review.", ""]
    (ROOT / "FAILURE_SHAPE_CENSUS.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Census reviewed Phase 0.2B false-positive shapes")
    parser.add_argument("--reviewer-a", required=True)
    parser.add_argument("--reviewer-b", required=True)
    args = parser.parse_args()
    design = run_census(args.reviewer_a, args.reviewer_b)
    print("CENSUS_COMPLETE", design["combined_counterfactual"])


if __name__ == "__main__":
    main()
