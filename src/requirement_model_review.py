"""Build the deterministic, evidence-backed Phase 0.3 model review artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output"
MAPPING_SHA = "3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a"
UNMATCHED_DIGEST = "07335ad502e4512712de0af6e4d8cd7fb0322d0a49952fc9826c8cc66b20c36f"
SOURCE_SET = {
    "scryfall": "0ce026779dae1a9a6448ef7a85e606d662343f5e",
    "forge": "cef86f363d7f7d5b3293248a75f550a7c3404066",
    "xmage": "6212eb37907c1ce751d8a3fea8b3322056dc0264",
}
STATUSES = {
    "counter": "RENAME_CANDIDATE",
    "counter_change": "PARAMETER_MODEL_NEEDS_REVIEW",
    "create_token": "PARAMETER_MODEL_NEEDS_REVIEW",
    "damage": "PARAMETER_MODEL_NEEDS_REVIEW",
    "destroy": "PARAMETER_MODEL_NEEDS_REVIEW",
    "discard": "PARAMETER_MODEL_NEEDS_REVIEW",
    "draw": "PARAMETER_MODEL_NEEDS_REVIEW",
    "gain_life": "PARAMETER_MODEL_NEEDS_REVIEW",
    "lose_life": "PARAMETER_MODEL_NEEDS_REVIEW",
    "mana_production": "PARAMETER_MODEL_NEEDS_REVIEW",
    "shuffle": "KEEP_AS_IS",
    "tap": "PARAMETER_MODEL_NEEDS_REVIEW",
    "untap": "PARAMETER_MODEL_NEEDS_REVIEW",
    "zone_transition": "PARAMETER_MODEL_NEEDS_REVIEW",
}
INTENTS = {
    "counter": "An operation that counters a target spell or ability, as represented by the current XMage mapping.",
    "counter_change": "An operation that places or changes counters on an existing object; mapped constructs currently expose counter placement.",
    "create_token": "Creation of one or more token objects with source-defined characteristics.",
    "damage": "Dealing a specified amount of damage to selected recipients.",
    "destroy": "Destroying selected objects that satisfy a source-defined selection.",
    "discard": "A player discarding selected cards from hand.",
    "draw": "A player drawing one or more cards.",
    "gain_life": "Increasing a player's life total by a source-defined amount.",
    "lose_life": "Decreasing a player's life total by a source-defined amount.",
    "mana_production": "Producing or adding mana with a source-defined kind, quantity, and restrictions.",
    "shuffle": "Randomizing the order of a library or other source-defined card set.",
    "tap": "Changing selected objects to tapped state.",
    "untap": "Changing selected objects to untapped state.",
    "zone_transition": "Moving an existing object from one zone to a different zone.",
}
EXCLUDED = {
    "counter": ["Placing counters on a permanent (counter_change)."],
    "counter_change": ["Countering a spell or ability (counter)."],
    "create_token": ["Moving an existing card between zones."],
    "damage": ["Destroying an object; damage and destroy are separate mapped operations."],
    "destroy": ["Damage without destruction."],
    "discard": ["Generic zone movement that is not explicitly mapped as a discard action."],
    "draw": ["Generic Library-to-Hand movement not explicitly represented by a draw construct."],
    "gain_life": ["Life loss (lose_life)."],
    "lose_life": ["Life gain (gain_life)."],
    "mana_production": ["Mana-cost payment or mana restrictions as standalone operations; current `Mana` path boundary is not fully validated."],
    "shuffle": ["Deterministic same-zone repositioning; shuffle is a distinct mapped operation."],
    "tap": ["Untapping objects (untap)."],
    "untap": ["Tapping objects (tap)."],
    "zone_transition": ["Same-zone repositioning, draw, discard, or shuffle as standalone operations."],
}
BOUNDARY_NOTES = {
    "counter": ["CounterTargetEffect occurrences counter a target spell/ability; counter placement is represented separately."],
    "counter_change": ["PutCounter and AddCountersSourceEffect expose type, quantity, and recipient; removal direction is not established by these mappings."],
    "create_token": ["Forge Token and XMage CreateTokenEffect are distinct paths; characteristics and quantity vary."],
    "damage": ["DealDamage/DamageTargetEffect and DamageAll variants vary in recipient selection and cardinality."],
    "destroy": ["Destroy/DestroyTargetEffect and DestroyAll variants vary in selection cardinality and modifiers."],
    "discard": ["Discard remains distinct from generic hand-to-graveyard movement; mapped path is unreviewed."],
    "draw": ["Draw remains distinct from generic library-to-hand movement; XMage path is unreviewed."],
    "gain_life": ["Life recipient and amount vary; one Forge evidence path remains unreviewed."],
    "lose_life": ["Life recipient and amount vary; both current paths remain unreviewed."],
    "mana_production": ["Forge fields include Produced, Amount, restrictions, persistence, and spend triggers; this path remains unreviewed."],
    "shuffle": ["Same-zone library rearrangement can have distinct shuffle versus positional semantics; current path remains unreviewed."],
    "tap": ["Tap as a cost and tap as an effect coexist in source scripts; path remains unreviewed."],
    "untap": ["Forge generic Untap and XMage UntapLandsEffect vary in selector scope; paths remain unreviewed."],
    "zone_transition": ["Observed movement paths vary in endpoints, selected set, cardinality, ownership/visibility, position, and timing."],
}
PARAMS = {
    "counter": [("countered_object", "REQUIRED", "Target spell or ability in observed cases", ["ValidTgts", "ValidCards", "Defined"]), ("eligibility", "OPTIONAL", "Target restrictions", ["ValidTgts", "ValidCards"])],
    "counter_change": [("counter_type", "REQUIRED", "Type of counter", ["CounterType"]), ("amount", "REQUIRED", "Count or expression", ["CounterNum"]), ("recipient", "REQUIRED", "Object receiving counters", ["ValidTgts", "ValidCards", "Defined"]), ("operation_direction", "NOT_ESTABLISHED", "Current mapped evidence primarily represents adding counters", ["PutCounter", "AddCountersSourceEffect"])],
    "create_token": [("token_definition", "REQUIRED", "Token identity and characteristics", ["TokenScript", "TokenPower", "TokenToughness", "TokenColor", "TokenTypes"]), ("quantity", "OPTIONAL", "Number created; some source operations default it", ["TokenAmount"]), ("owner_or_controller", "SOURCE_SPECIFIC", "Creator, owner, or controller where represented", ["TokenOwner", "Defined"]), ("entry_modifiers", "SOURCE_SPECIFIC", "Tapped or other entry state", ["TokenTapped", "TokenScript"])],
    "damage": [("amount", "REQUIRED", "Fixed or source-derived amount", ["NumDmg"]), ("recipient_selection", "REQUIRED", "Targets, filters, or defined recipients", ["ValidTgts", "ValidCards", "ValidPlayers", "Defined"]), ("cardinality_distribution", "SOURCE_SPECIFIC", "Single/all and divided allocation", ["TargetMin", "TargetMax", "DividedAsYouChoose"]), ("damage_source", "OPTIONAL", "Credited source when exposed", ["DamageSource"])],
    "destroy": [("object_selection", "REQUIRED", "Target/filter/defined object group", ["ValidTgts", "ValidCards", "Defined"]), ("cardinality", "REQUIRED", "Single, many, or all matching objects", ["TargetMin", "TargetMax", "ValidCards"]), ("modifiers", "SOURCE_SPECIFIC", "Flags such as NoRegen or remembered LKI", ["NoRegen", "RememberLKI", "RememberDestroyed"])],
    "discard": [("discarding_player", "REQUIRED", "Player who discards", ["ValidTgts", "ValidPlayers", "Defined"]), ("card_selection", "REQUIRED", "Chosen or filtered cards", ["DiscardValid", "Mode", "Defined"]), ("quantity", "REQUIRED", "Number or all", ["NumCards", "Mode"]), ("choice_and_reveal", "SOURCE_SPECIFIC", "Choice/reveal behavior", ["Mode", "RevealDiscardAll"])],
    "draw": [("drawing_player", "REQUIRED", "Player receiving cards", ["Defined", "ValidTgts", "ValidPlayers"]), ("quantity", "REQUIRED", "Number of cards", ["NumCards"]), ("conditionality", "SOURCE_SPECIFIC", "Conditions and optional choice", ["ConditionPresent", "OptionalDecider"])],
    "gain_life": [("life_recipient", "REQUIRED", "Player whose life total changes", ["Defined", "ValidTgts", "ValidPlayers"]), ("amount", "REQUIRED", "Fixed or source-derived amount", ["LifeAmount"])],
    "lose_life": [("life_recipient", "REQUIRED", "Player whose life total changes", ["Defined", "ValidTgts", "ValidPlayers"]), ("amount", "REQUIRED", "Fixed or source-derived amount", ["LifeAmount"])],
    "mana_production": [("mana_kind_or_choice", "REQUIRED", "Produced kind/color or choice", ["Produced"]), ("quantity", "REQUIRED", "Units or source expression", ["Amount", "Produced"]), ("restriction_and_duration", "SOURCE_SPECIFIC", "Spending restrictions or persistence", ["RestrictValid", "PersistentMana", "TriggersWhenSpent"])],
    "shuffle": [("shuffled_library_or_set", "REQUIRED", "Library or defined card set", ["Defined", "ValidTgts", "ValidCards"]), ("timing_or_choice", "SOURCE_SPECIFIC", "Ability/subability/optional context", ["Mode", "Optional", "SubAbility"])],
    "tap": [("object_selection", "REQUIRED", "Object or set being tapped", ["ValidTgts", "ValidCards", "Defined"]), ("cardinality", "SOURCE_SPECIFIC", "Target count or all/up-to selection", ["TargetMin", "TargetMax", "ChangeNum"]), ("cost_or_effect", "SOURCE_SPECIFIC", "Tap as cost versus effect", ["Cost", "DB", "SP", "AB"])],
    "untap": [("object_selection", "REQUIRED", "Object or set being untapped", ["ValidTgts", "ValidCards", "Defined"]), ("cardinality", "SOURCE_SPECIFIC", "Target count or land-specific selection", ["ChangeNum", "ValidCards", "UntapLandsEffect"]), ("timing_context", "SOURCE_SPECIFIC", "Ability and condition context", ["DB", "AB", "ConditionPresent"])],
    "zone_transition": [("origin", "REQUIRED", "Source zone", ["Origin"]), ("destination", "REQUIRED", "Different destination zone; 0.2.1 suppresses equal parsed zones", ["Destination"]), ("object_selection", "REQUIRED", "Target/filter/defined object group", ["ValidTgts", "ValidCards", "ChangeType", "Defined"]), ("cardinality", "REQUIRED", "One/count/all/up-to", ["ChangeNum", "TargetMin", "TargetMax"]), ("owner_controller_visibility", "SOURCE_SPECIFIC", "Ownership, chooser, visibility, reveal, memory", ["DefinedPlayer", "Chooser", "Hidden", "Reveal", "RememberChanged"]), ("position_order", "SOURCE_SPECIFIC", "Library position or order", ["LibraryPosition", "RandomOrder"]), ("timing_context", "SOURCE_SPECIFIC", "Trigger/activation timing", ["Mode", "TriggerZones"])],
}


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def source_mappings():
    mappings = yaml.safe_load((ROOT / "mappings.yaml").read_text(encoding="utf-8"))
    result = defaultdict(list)
    for source in ("forge", "xmage"):
        for construct, req in mappings[source].items():
            result[req].append((source, construct))
    return dict(result)


def build():
    mapping_path = ROOT / "mappings.yaml"
    if hashlib.sha256(mapping_path.read_bytes()).hexdigest() != MAPPING_SHA:
        raise ValueError("mappings.yaml SHA-256 differs from the pinned review scope")
    profile_doc = yaml.safe_load((ROOT / "requirement_evidence_projection.yaml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load((ROOT / "requirement_evidence_projection_manifest.yaml").read_text(encoding="utf-8"))
    if manifest["extractor_version"] != "0.2.1" or manifest["source_set"] != SOURCE_SET or manifest["mapping_sha256"] != MAPPING_SHA:
        raise ValueError("Projection manifest is outside the pinned Phase 0.3 scope")
    historical_validation = yaml.safe_load((ROOT / "validation_results.yaml").read_text(encoding="utf-8"))
    validation_transfer = yaml.safe_load((ROOT / "extractor_0_2_1_validation_transfer.yaml").read_text(encoding="utf-8"))
    differential_validation = yaml.safe_load((ROOT / "differential_validation_results.yaml").read_text(encoding="utf-8"))
    projection_report = (ROOT / "REQUIREMENT_EVIDENCE_PROJECTION_REPORT.md").read_text(encoding="utf-8")
    if historical_validation["validation_scope"]["extractor_version"] != "0.2.0" or historical_validation["review_batch_id"] != "phase-0.2a-batch-1":
        raise ValueError("Historical pattern validation is not the expected 0.2.0 review batch")
    if validation_transfer["status"] != "DIFFERENTIAL_VALIDATION_COMPLETE" or validation_transfer["extractor_version"] != "0.2.1" or validation_transfer["source_set"] != SOURCE_SET or validation_transfer["mapping_sha256"] != MAPPING_SHA or validation_transfer["unchanged_identity"]["match"] is not True:
        raise ValueError("Extractor 0.2.1 validation transfer is incomplete")
    if differential_validation["status"] != "DIFFERENTIAL_VALIDATION_COMPLETE" or differential_validation["validation_scope"]["source_set"] != SOURCE_SET or differential_validation["validation_scope"]["mapping_sha256"] != MAPPING_SHA or differential_validation["differential_population"]["removed_occurrences"] != 104 or differential_validation["differential_population"]["added_occurrences"] != 0:
        raise ValueError("Differential validation artifacts do not certify the expected changed population")
    if "36,923" not in projection_report or "29,182" not in projection_report:
        raise ValueError("Projection report does not describe the pinned card/occurrence population")
    requirements = set(profile_doc["requirements"])
    mappings = source_mappings()
    if requirements != set(mappings) or requirements != set(INTENTS) or len(requirements) != 14:
        raise ValueError(f"Unexpected Requirement set: {sorted(requirements)}")
    path_profiles = {}
    all_paths = []
    for req, config in profile_doc["requirements"].items():
        for source in ("forge", "xmage"):
            for path in config["evidence_paths"].get(source, []):
                path_profiles[path["evidence_path_id"]] = path
                all_paths.append((req, source, path))
        for path in config.get("cross_corroboration", []):
            all_paths.append((req, "cross_engine", path))
    source_path_ids = [path["evidence_path_id"] for _, source, path in all_paths if source in {"forge", "xmage"}]
    if len(source_path_ids) != 29 or len(set(source_path_ids)) != 29:
        raise ValueError("Source evidence path IDs must be unique and exactly 29")
    if len(all_paths) != 31:
        raise ValueError(f"Expected 29 source paths + 2 cross-engine paths; found {len(all_paths)}")

    path_constructs = {(s, c, r) for r, vals in mappings.items() for s, c in vals}
    profile_constructs = {
        (source, path["external_construct"], req)
        for req, source, path in all_paths
        if source in {"forge", "xmage"}
    }
    if path_constructs != profile_constructs or len(profile_constructs) != 29:
        raise ValueError("Active source evidence paths do not assign every current mapping exactly once")
    occurrence_counts = Counter()
    distinct_cards = defaultdict(set)
    parameter_counts = Counter()
    param_values = defaultdict(Counter)
    examples = defaultdict(list)
    pair_source_counts = Counter()
    totals = Counter()
    unresolved_cards = 0
    warning_cards = set()
    card_requirement_counts = Counter()
    boundary_pair_examples = defaultdict(list)
    zone_pairs = Counter()
    zone_pair_examples = defaultdict(list)
    for card in read_jsonl(OUT / "card_requirement_evidence.jsonl"):
        totals["cards"] += 1
        if card.get("unresolved_evidence"):
            unresolved_cards += 1
        if card.get("summary", {}).get("source_warnings"):
            warning_cards.add(card["oracle_id"])
        reqs = {r["requirement_id"]: r for r in card.get("requirements", [])}
        for req_id, req in reqs.items():
            totals["pairs"] += 1
            card_requirement_counts[req_id] += 1
            sources = set()
            for path in req["evidence_paths"]:
                sources.add(path["source"])
                for occurrence in path["occurrences"]:
                    totals["occurrences"] += 1
                    occurrence_counts[path["evidence_path_id"]] += 1
                    distinct_cards[path["evidence_path_id"]].add(card["oracle_id"])
                    for key, vals in (occurrence.get("action_local_parameters") or {}).items():
                        vals = vals if isinstance(vals, list) else [vals]
                        parameter_counts[(req_id, key)] += 1
                        param_values[(req_id, key)].update(str(v) for v in vals)
                    if req_id == "zone_transition":
                        params = occurrence.get("action_local_parameters") or {}
                        origin = params.get("Origin") or []
                        destination = params.get("Destination") or []
                        if len(origin) == 1 and len(destination) == 1:
                            pair = (str(origin[0]), str(destination[0]))
                            zone_pairs[pair] += 1
                            if len(zone_pair_examples[pair]) < 2:
                                zone_pair_examples[pair].append({"oracle_id": card["oracle_id"], "card_name": card["card_name"], "source": occurrence["source"], "source_record_identity": occurrence["source_record_identity"], "external_construct": occurrence["external_construct"], "occurrence_identity": occurrence["occurrence_identity"], "action_local_parameters": params})
                    identity = occurrence["occurrence_identity"]["id"]
                    rank = hashlib.sha256((path["evidence_path_id"] + "|" + identity).encode()).hexdigest()
                    ex = {
                        "oracle_id": card["oracle_id"], "card_name": card["card_name"],
                        "type_line": card.get("oracle_source", {}).get("type_line"),
                        "layout": card.get("oracle_source", {}).get("layout"),
                        "oracle_text": card.get("oracle_source", {}).get("oracle_text"),
                        "faces": card.get("oracle_source", {}).get("faces", []),
                        "source": occurrence["source"], "source_record_identity": occurrence["source_record_identity"],
                        "external_construct": occurrence["external_construct"], "requirement_id": req_id,
                        "evidence_path_id": path["evidence_path_id"], "occurrence_identity": occurrence["occurrence_identity"],
                        "extractor_version": occurrence["extractor_version"],
                        "source_revision": occurrence["source_revision"],
                        "source_match_method": occurrence.get("source_match_method"),
                        "historical_validation_pattern_ids": occurrence.get("historical_validation_pattern_ids", []),
                        "occurrence_transfer": occurrence.get("occurrence_transfer"),
                        "action_local_parameters": occurrence.get("action_local_parameters"),
                        "java_usage_classification": occurrence.get("java_usage_classification"),
                        "evidence_excerpt": occurrence.get("raw_action_snippet") or occurrence.get("java_excerpt"),
                        "join_warning": occurrence.get("join_warning"),
                        "card_source_warnings": card.get("summary", {}).get("source_warnings", []),
                    }
                    examples[path["evidence_path_id"]].append((rank, ex))
            pair_source_counts["multi"] += sources == {"forge", "xmage"}
            pair_source_counts["forge_only"] += sources == {"forge"}
            pair_source_counts["xmage_only"] += sources == {"xmage"}
        # Deterministic positive and overlap boundaries from observed card-level co-occurrence.
        for left, right, label in [("counter", "counter_change", "counter_vs_counter_change"), ("draw", "zone_transition", "draw_vs_zone_transition"), ("discard", "zone_transition", "discard_vs_zone_transition"), ("shuffle", "zone_transition", "shuffle_vs_same_zone"), ("gain_life", "lose_life", "gain_vs_lose_life"), ("tap", "untap", "tap_vs_untap")]:
            if left in reqs and right in reqs and len(boundary_pair_examples[label]) < 3:
                boundary_pair_examples[label].append({"oracle_id": card["oracle_id"], "card_name": card["card_name"], "oracle_text": card.get("oracle_source", {}).get("oracle_text"), "requirements": [{"requirement_id": rid, "evidence": [{"oracle_id": card["oracle_id"], "source": occ["source"], "source_record_identity": occ["source_record_identity"], "external_construct": occ["external_construct"], "occurrence_identity": occ["occurrence_identity"]} for path in reqs[rid]["evidence_paths"] for occ in path["occurrences"][:2]]} for rid in (left, right)]})

    # Load all source-backed examples; pick stable low-hash representatives.
    examples_out = {}
    for req, source, path in all_paths:
        if source == "cross_engine":
            continue
        pid = path["evidence_path_id"]
        rows = sorted(examples[pid], key=lambda row: (row[0], row[1]["oracle_id"], row[1]["occurrence_identity"]["id"]))
        # Prefer distinct cards and observable type/layout variety.
        selected, seen_cards, seen_strata = [], set(), set()
        for _, ex in rows:
            stratum = (ex.get("type_line"), ex.get("layout"))
            if ex["oracle_id"] not in seen_cards and (not selected or stratum not in seen_strata):
                selected.append(ex); seen_cards.add(ex["oracle_id"]); seen_strata.add(stratum)
            if len(selected) == 3:
                break
        for _, ex in rows:
            if len(selected) >= 3: break
            if ex["oracle_id"] not in seen_cards:
                selected.append(ex); seen_cards.add(ex["oracle_id"])
        examples_out[pid] = {"population_occurrences": occurrence_counts[pid], "distinct_oracle_ids": len(distinct_cards[pid]), "representative_examples": selected}

    reviewed = {}
    params_doc = {"review_version": 1, "scope": {"extractor_version": "0.2.1", "mapping_sha256": MAPPING_SHA, "source_set": SOURCE_SET}, "requirements": {}}
    boundary_doc = {"review_version": 1, "scope": {"extractor_version": "0.2.1", "source_set": SOURCE_SET}, "requirements": {}}
    evidence_refs = {}
    overlap_map = {
        "counter": ["counter_change"], "counter_change": ["counter"],
        "draw": ["zone_transition"], "zone_transition": ["draw", "discard", "shuffle"],
        "discard": ["zone_transition"], "shuffle": ["zone_transition"],
        "gain_life": ["lose_life"], "lose_life": ["gain_life"],
        "tap": ["untap"], "untap": ["tap"],
    }
    for req in sorted(requirements):
        paths = [(src, path) for r, src, path in all_paths if r == req and src != "cross_engine"]
        bysrc = {src: [p["evidence_path_id"] for s, p in paths if s == src] for src in ("forge", "xmage")}
        validated = [p["evidence_path_id"] for _, p in paths if p["status"] in {"REVIEW_COMPLETE", "DIFFERENTIAL_VALIDATION_COMPLETE"}]
        unreviewed = [p["evidence_path_id"] for _, p in paths if p["status"] == "UNREVIEWED"]
        refs = []
        for _, p in paths:
            refs.extend(examples_out[p["evidence_path_id"]]["representative_examples"][:2])
        reviewed[req] = {
            "primary_status": STATUSES[req],
            "semantic_intent": INTENTS[req],
            "evidence_path_consistency": {"status": "CONSISTENT_WITHIN_CURRENT_MAPPING_SCOPE", "note": "Construct-to-Requirement patterns are distinct evidence paths; unreviewed paths remain unvalidated, not presumed inconsistent."},
            "included_behaviors": [INTENTS[req]],
            "excluded_behaviors": EXCLUDED[req] + ["No inference about absent Magic capability, complete card semantics, or rules correctness."],
            "current_evidence_paths": {s: bysrc[s] for s in ("forge", "xmage")},
            "cross_engine_corroboration_patterns": [p["pattern_id"] for r, src, p in all_paths if r == req and src == "cross_engine"],
            "evidence_path_metadata": [{"evidence_path_id": p["evidence_path_id"], "source": src, "external_construct": p["external_construct"], "status": p["status"], "validation_pattern_ids": p.get("validation_pattern_ids", []), "historical_validation": p.get("historical_validation"), "extractor_0_2_1_population_status": p.get("extractor_0_2_1_population_status")} for src, p in paths],
            "validated_paths": validated,
            "unreviewed_paths": unreviewed,
            "representative_evidence": refs[:6],
            "parameter_findings": [
                {"name": name, "necessity": necessity, "observed_fields": fields, "evidence": [p for _, p in paths]}
                for name, necessity, _, fields in PARAMS[req]
            ],
            "boundary_findings": BOUNDARY_NOTES[req],
            "overlap_candidates": [{"requirement_id": other, "observed_relationship": "CARD_LEVEL_CO_OCCURRENCE", "evidence_catalog": f"{req}__{other}"} for other in overlap_map.get(req, [])],
            "decomposition_pressure": "PARAMETERIZATION_REVIEW" if STATUSES[req] == "PARAMETER_MODEL_NEEDS_REVIEW" else "LOW_FROM_CURRENT_EVIDENCE",
            "merge_pressure": "LOW_NO_DEMONSTRATED_INFORMATION_PRESERVING_MERGE" if req in {"draw", "discard", "shuffle", "gain_life", "lose_life", "tap", "untap", "counter", "counter_change"} else "NOT_INDICATED",
            "model_gaps": [],
            "normative_rules_dependency": {"status": "DEFERRED_FOR_RULES_LEVEL_CLAIMS", "questions": ["Exact comprehensive-rules semantics, replacement/prevention interactions, and timing details require normative rules review where relevant."]},
            "compatibility_impact": {"mapping_impact": "Requirement identifier remains unchanged; any future change may require mapping revisions.", "projection_impact": "Parameter changes may require a versioned projection schema update.", "review_result_impact": "Historical results remain scoped to their existing extractor and pattern identities.", "sample_id_impact": "No sample IDs change in this phase.", "future_sqlite_impact": "Potential columns/relations should preserve parameters and evidence paths."},
            "recommended_next_action": "Review the named parameter contract before expanding mappings or declaring model stability.",
        }
        params_doc["requirements"][req] = {
            "semantic_intent": INTENTS[req],
            "parameters": [{"name": name, "necessity": necessity, "description": desc, "observed_source_fields": fields, "observed_occurrence_count": sum(parameter_counts[(req, f)] for f in fields), "observed_values": {field: [{"value": val, "count": count} for val, count in param_values[(req, field)].most_common(12)] for field in fields}} for name, necessity, desc, fields in PARAMS[req]],
            "unknown_or_unmodeled": ["The projection currently preserves occurrence-local source parameters; no normalized Requirement parameter contract is enforced."],
            "semantic_loss_risk": req != "shuffle",
        }
        boundary_doc["requirements"][req] = {
            "positive_examples": refs[:4],
            "excluded_or_boundary_examples": [],
            "unresolved_questions": ["Normative rules interpretation is outside this phase."],
        }
        evidence_refs[req] = refs

    # Attach evidence-backed co-occurrence boundaries.
    boundary_doc["relationship_examples"] = dict(boundary_pair_examples)
    # Historical guard evidence is retained as explicitly inactive context.
    historical = []
    audit_path = OUT / "differential_review_samples.jsonl"
    if audit_path.exists():
        for row in read_jsonl(audit_path):
            if row.get("guard_type") == "FORGE_SAME_ZONE":
                ident = row["old_occurrence_identity"]
                historical.append({"oracle_id": ident["oracle_id"], "card_name": row.get("card_name"), "source": "forge", "source_record_identity": ident["source_record_identity"], "external_construct": ident["external_construct"], "requirement_id": ident["requirement"], "differential_sample_id": row["differential_sample_id"], "status": "HISTORICAL_REMOVAL_NOT_ACTIVE_EVIDENCE"})
    boundary_doc["historical_inactive_zone_same_zone_examples"] = sorted(historical, key=lambda r: r["differential_sample_id"])[:4]
    # Encode key ontology boundaries without asserting semantic equivalence from co-occurrence.
    boundary_doc["cross_requirement_boundaries"] = {
        "counter_vs_counter_change": {"finding": "Observed counter-spell/ability evidence is distinct from counter placement evidence; names can be confused.", "examples": boundary_pair_examples.get("counter_vs_counter_change", [])},
        "draw_vs_zone_transition": {"finding": "Draw is mapped as its own operation; some cards also have separate zone movement evidence.", "examples": boundary_pair_examples.get("draw_vs_zone_transition", [])},
        "discard_vs_zone_transition": {"finding": "Discard is separately represented; co-occurrence with movement does not imply interchangeability.", "examples": boundary_pair_examples.get("discard_vs_zone_transition", [])},
        "shuffle_vs_same_zone": {"finding": "Shuffle is a distinct action, not an inferred Library-to-Library transition; same-zone repositioning is excluded by the 0.2.1 guard.", "examples": boundary_pair_examples.get("shuffle_vs_same_zone", [])},
        "gain_vs_lose_life": {"finding": "Opposite direction operations have separate identifiers; a signed abstraction has no demonstrated analysis benefit here.", "examples": boundary_pair_examples.get("gain_vs_lose_life", [])},
        "tap_vs_untap": {"finding": "Opposite state changes remain separate; observed symmetry alone does not justify merging.", "examples": boundary_pair_examples.get("tap_vs_untap", [])},
    }
    boundary_doc["requirements"]["zone_transition"]["observed_zone_pairs"] = [
        {"origin": pair[0], "destination": pair[1], "occurrences": count, "examples": zone_pair_examples[pair]}
        for pair, count in sorted(zone_pairs.items(), key=lambda item: (-item[1], item[0]))[:20]
    ]
    # Census a small set of frequent unmapped constructs as model-gap leads, never mappings.
    gap_tokens = {
        "forge": {"ChangesZone", "Pump", "DamageDone"},
        "xmage": {"BoostTargetEffect", "BoostSourceEffect"},
    }
    gap_counts = Counter()
    gap_examples = defaultdict(list)
    for card in read_jsonl(OUT / "requirement_candidates.jsonl"):
        for item in card.get("unmapped_evidence", []):
            source, token = item.get("source"), item.get("token")
            if token not in gap_tokens.get(source, set()):
                continue
            gap_counts[(source, token)] += 1
            if len(gap_examples[(source, token)]) < 3:
                from src.cap_miner import reviewable_record_identity
                ref = {
                    "oracle_id": card["oracle_id"], "card_name": card.get("name"),
                    "source": source, "source_record_identity": reviewable_record_identity(source, SOURCE_SET[source], item["source_record_index"]),
                    "external_construct": token, "occurrence_index": item.get("occurrence_index"),
                }
                gap_examples[(source, token)].append(ref)
    gap_descriptions = {
        ("forge", "ChangesZone"): "Observed zone-change event/trigger vocabulary, distinct from an action that performs a zone transition.",
        ("forge", "Pump"): "Observed power/toughness modification vocabulary not represented by the current Requirement set.",
        ("forge", "DamageDone"): "Observed damage-event vocabulary; relation to damage action evidence needs explicit modeling review.",
        ("xmage", "BoostTargetEffect"): "Observed target power/toughness modification implementation class.",
        ("xmage", "BoostSourceEffect"): "Observed source power/toughness modification implementation class.",
    }
    model_gaps = []
    for (source, token), count in sorted(gap_counts.items()):
        model_gaps.append({
            "gap_id": f"potential:{source}:{token}", "source": source,
            "external_construct": token, "observed_unmapped_occurrences": count,
            "example_oracle_ids": [x["oracle_id"] for x in gap_examples[(source, token)]],
            "examples": gap_examples[(source, token)], "description": gap_descriptions[(source, token)],
            "reason_current_requirements_do_not_fit": "No current mapping assigns this observed construct; no Requirement is inferred in Phase 0.3.",
            "normative_rules_review_required": True,
        })
    boundary_doc["potential_model_gaps"] = model_gaps
    # Record potential gaps centrally; they are leads, not new Requirement identifiers.
    model_gaps_count = len(model_gaps)
    status_counts = Counter(STATUSES.values())
    summary = {
        "requirements_reviewed": len(reviewed), "evidence_paths_reviewed": len(path_profiles),
        "source_evidence_paths": len(path_profiles),
        "validated_paths": sum(p["status"] == "REVIEW_COMPLETE" for p in path_profiles.values()),
        "unreviewed_paths": sum(p["status"] == "UNREVIEWED" for p in path_profiles.values()),
        "primary_status_counts": dict(sorted(status_counts.items())),
        "card_requirement_pairs": totals["pairs"], "active_occurrences": totals["occurrences"],
        "cards_with_unresolved_evidence": unresolved_cards, "cards_with_join_warnings": len(warning_cards),
        "potential_model_gaps": model_gaps_count,
        "potential_overlaps": 6,
        "normative_rules_questions_deferred": 14,
        "model_corrections_required": any(x in STATUSES.values() for x in ("PARAMETER_MODEL_NEEDS_REVIEW", "SPLIT_CANDIDATE", "MERGE_CANDIDATE", "RENAME_CANDIDATE")),
    }
    model_doc = {"review_version": 1, "scope": {"extractor_version": "0.2.1", "source_set": SOURCE_SET, "mapping_sha256": MAPPING_SHA, "differential_validation_status": "DIFFERENTIAL_VALIDATION_COMPLETE", "unchanged_occurrence_identity_digest": UNMATCHED_DIGEST}, "summary": summary, "requirements": reviewed, "potential_model_gaps": model_gaps}
    summary["parent_review_batch_id"] = historical_validation["review_batch_id"]
    summary["parent_validation_extractor"] = historical_validation["validation_scope"]["extractor_version"]
    summary["parent_final_correct"] = historical_validation["primary_final_counts"]["CORRECT"]
    summary["parent_final_wrong"] = historical_validation["primary_final_counts"]["WRONG"]
    summary["differential_validation_status"] = differential_validation["status"]
    return model_doc, params_doc, boundary_doc, examples_out, summary, profile_doc


def write_outputs():
    model, params, boundaries, examples, summary, profile = build()
    outputs = {
        "requirement_model_review.yaml": model,
        "requirement_parameter_contracts.yaml": params,
        "requirement_boundary_cases.yaml": boundaries,
    }
    for name, data in outputs.items():
        (ROOT / name).write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
    report = make_report(model, examples, summary, profile)
    (ROOT / "REQUIREMENT_MODEL_REVIEW_REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    return outputs, report


def make_report(model, examples, summary, profile):
    lines = ["# Requirement Model Review", "", "## Scope", "", "Review of the current Requirement primitives using only pinned repository evidence and existing validation metadata. No rules authority was fetched or integrated.", "", "## Current Requirement model", "", f"Reviewed {summary['requirements_reviewed']} current Requirements and {summary['source_evidence_paths']} source evidence paths ({summary['validated_paths']} reviewed paths, {summary['unreviewed_paths']} unreviewed paths).", "", "## Review methodology", "", "Representative occurrences are selected by stable SHA-256 ordering of evidence path ID plus occurrence identity, with basic type/layout diversity. Counts refer to active occurrence populations in the card projection. Historical precision remains scoped to extractor 0.2.0; 0.2.1 transfer is exact-identity metadata only. No precision is combined at Requirement level.", "", "## Requirement-by-Requirement findings", "", "| Requirement | Evidence paths | Validated | Unreviewed | Primary status | Parameter issue | Overlap/boundary | Rules review |", "|---|---:|---:|---:|---|---|---|---|"]
    for req in sorted(model["requirements"]):
        r = model["requirements"][req]
        paths = r["current_evidence_paths"]["forge"] + r["current_evidence_paths"]["xmage"]
        lines.append(f"| `{req}` | {len(paths)} | {len(r['validated_paths'])} | {len(r['unreviewed_paths'])} | {r['primary_status']} | {len(r['parameter_findings'])} dimensions | see boundary catalog | deferred where normative |")
        lines.extend(["", f"### `{req}`", "", f"**Intent:** {r['semantic_intent']}", "", f"**Status:** `{r['primary_status']}`. {r['recommended_next_action']}", "", "**Observed paths:** " + (", ".join(f"`{p}`" for p in paths) or "none"), "", "**Validation state:** validated paths: " + (", ".join(f"`{p}`" for p in r["validated_paths"]) or "none") + "; unreviewed paths: " + (", ".join(f"`{p}`" for p in r["unreviewed_paths"]) or "none") + ". Unreviewed means not validated, not inconsistent.", "", "**Parameter findings:** " + "; ".join(f"`{p['name']}` ({p['necessity']}; source fields: {', '.join(p['observed_fields'])})" for p in r["parameter_findings"]), "", "**Representative evidence:**"])
        for ex in r["representative_evidence"][:2]:
            lines.append(f"- {ex['card_name']} (`{ex['oracle_id']}`), {ex['source']} `{ex['external_construct']}`, record `{ex['source_record_identity']}`, occurrence `{ex['occurrence_identity']['id']}`; parameters `{json.dumps(ex.get('action_local_parameters'), ensure_ascii=False, sort_keys=True)[:240]}`.")
        if not r["representative_evidence"]:
            lines.append("- No source-backed example was available in the active projection.")
        lines.append("")
    lines.extend(["## Parameter-model findings", "", "The projection preserves source-local parameters, but a Requirement ID alone cannot reconstruct amounts, selectors, cardinality, object recipient, counter/token definition, mana restrictions, or zone endpoints. The parameter contract records observed dimensions; it does not assert Comprehensive Rules requirements.", "", "## Semantic boundary findings", "", "- `counter` denotes countering a spell or ability in the current mapped examples; `counter_change` denotes placing counters. Keep separate; `counter` is a rename candidate because its bare name is easy to confuse with counter placement.", "- `zone_transition` denotes movement between distinct zones. Same-zone library repositioning is historical excluded evidence under 0.2.1, not active evidence.", "- `draw` and `discard` are distinct mapped actions even when a card also has Library/Hand/Graveyard movement evidence.", "- `shuffle` is a distinct action and not a generic Library-to-Library transition.", "- `damage` and `destroy` each group single-target and all-style constructs; current evidence suggests selection/cardinality parameters can retain that distinction.", "- `tap`/`untap` and `gain_life`/`lose_life` are directional operations. A signed/shared abstraction has no concrete demonstrated benefit.", "", "## Requirement overlap findings", "", "Co-occurrence is not semantic equivalence. The boundary catalog contains deterministic source-backed Oracle-ID examples for counter/counter_change, draw/zone_transition, discard/zone_transition, shuffle/zone_transition, life direction, and tap direction. No merge or split is recommended from these overlaps alone.", "", "## Potential model gaps", "", f"The deterministic unmapped-evidence scan found {len(model['potential_model_gaps'])} candidate vocabulary gaps. They remain unassigned and do not imply full-corpus ontology coverage:", ""])
    for gap in model["potential_model_gaps"]:
        lines.append(f"- `{gap['source']}:{gap['external_construct']}` ({gap['observed_unmapped_occurrences']} occurrences): {gap['description']} Example `{gap['examples'][0]['card_name']}` (`{gap['examples'][0]['oracle_id']}`), source record `{gap['examples'][0]['source_record_identity']}`.")
    lines.extend(["", "## Special audits", "", "- **counter vs counter_change:** counter means countering a spell/ability in current examples; counter_change covers placing counters. Keep distinct; `counter` is a rename candidate due to ambiguity.", "- **zone_transition:** coherent for distinct zone endpoints, with parameter-model review needed for selection, cardinality, visibility/ownership, position, and timing. Four adjudicated same-zone failures remain historical inactive evidence.", "- **damage:** target and all-style paths appear parameterizable by recipient set, amount, cardinality, and distribution.", "- **destroy:** target and all-style paths appear parameterizable by selection/cardinality/modifiers. The old import-only issue was extraction-level and is not reopened.", "- **draw vs zone_transition:** preserve distinct mapped operations; co-occurrence does not merge them.", "- **discard vs zone_transition:** preserve explicit discard as distinct from generic zone movement.", "- **shuffle vs same-zone:** Shuffle is a distinct operation; equal-endpoint zone actions do not enter active zone_transition evidence under 0.2.1.", "- **gain/lose life and tap/untap:** keep directional operations separate; no concrete benefit from a signed/shared abstraction is shown.", ""])
    lines.extend(["", "## Unreviewed evidence-path implications", "", "Sixteen source paths remain unreviewed. Their observed constructs inform boundary and parameter inspection, but they are not marked validated or inconsistent and no statistical review packet was produced.", "", "## Normative rules questions deferred", "", "Exact Magic rules semantics, replacement/prevention interactions, layers, timing, and edge conditions need normative rules review where a later use requires those claims. This report makes no rules-correctness determination.", "", "## Compatibility impact", "", "No IDs, mappings, extractor behavior, projection, validation results, or samples changed. Future parameter normalization may affect projection schema and downstream persisted artifacts; renaming `counter` affects its mapping path, 145 card-Requirement pairs, review-pattern identity and future persisted IDs. Historical review remains tied to its prior scope.", "", "## Recommended next phase", "", "**PHASE_0_3_1_REQUIREMENT_MODEL_CORRECTIONS** — review parameter contracts and decide whether to version the `counter` name before expanding validation. The current evidence identifies material parameter-representation gaps; no correction is made here.", "", "## Summary classifications", "", json.dumps(summary["primary_status_counts"], sort_keys=True), "", "**MODEL_CORRECTIONS_REQUIRED = true**. This is a review recommendation, not an applied model change.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.write:
        parser.error("Use --write to generate the review artifacts")
    write_outputs()


if __name__ == "__main__":
    main()
