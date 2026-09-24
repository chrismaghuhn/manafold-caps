import hashlib
import json
from pathlib import Path

import yaml

from src import requirement_model_review as review


def test_review_covers_exact_current_requirements_and_paths():
    model, params, boundaries, examples, summary, profile = review.build()
    mappings = review.source_mappings()
    assert set(model["requirements"]) == set(mappings)
    assert len(model["requirements"]) == 14
    assert all(item["primary_status"] in set(review.STATUSES.values()) for item in model["requirements"].values())
    assert all(item["semantic_intent"] and "included_behaviors" in item and "excluded_behaviors" in item for item in model["requirements"].values())
    assert set(params["requirements"]) == set(model["requirements"])
    assert set(boundaries["requirements"]) == set(model["requirements"])
    assert summary["evidence_paths_reviewed"] == 29
    assert summary["validated_paths"] == 13
    assert summary["unreviewed_paths"] == 16
    assert sum(summary["primary_status_counts"].values()) == 14


def test_boundary_examples_have_stable_source_provenance():
    _, _, boundaries, _, _, _ = review.build()
    for requirement in boundaries["requirements"].values():
        for example in requirement.get("positive_examples", []):
            assert example.get("oracle_id")
            assert example.get("source") in {"forge", "xmage"}
            assert example.get("source_record_identity")
            assert example.get("external_construct")
            assert example.get("occurrence_identity", {}).get("id")
    for relation_examples in boundaries["relationship_examples"].values():
        for example in relation_examples:
            for req in example["requirements"]:
                assert req["evidence"]
                assert all(e.get("oracle_id") == example["oracle_id"] for e in req["evidence"])
                assert all(e.get("source_record_identity") and e.get("external_construct") for e in req["evidence"])


def test_scope_and_source_artifacts_are_unchanged():
    assert hashlib.sha256((review.ROOT / "mappings.yaml").read_bytes()).hexdigest() == review.MAPPING_SHA
    manifest = yaml.safe_load((review.ROOT / "requirement_evidence_projection_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["extractor_version"] == "0.2.1"
    assert manifest["mapping_sha256"] == review.MAPPING_SHA
    profile = yaml.safe_load((review.ROOT / "requirement_evidence_projection.yaml").read_text(encoding="utf-8"))
    assert set(profile["requirements"]) == set(review.STATUSES)


def test_generated_artifacts_are_deterministic():
    first = review.write_outputs()
    paths = [review.ROOT / name for name in ("requirement_model_review.yaml", "requirement_parameter_contracts.yaml", "requirement_boundary_cases.yaml", "REQUIREMENT_MODEL_REVIEW_REPORT.md")]
    before = [path.read_bytes() for path in paths]
    review.write_outputs()
    after = [path.read_bytes() for path in paths]
    assert before == after
    assert first[1] == paths[-1].read_text(encoding="utf-8")


def test_review_does_not_change_requirement_ids_or_validation_artifacts():
    expected = {"validation_results.yaml", "extractor_0_2_1_validation_transfer.yaml", "differential_validation_results.yaml"}
    assert expected <= {p.name for p in review.ROOT.iterdir()}
    assert review.build()[4]["requirements_reviewed"] == 14
    projection = yaml.safe_load((review.ROOT / "requirement_evidence_projection.yaml").read_text(encoding="utf-8"))
    assert projection["summary"]["active_source_evidence_paths"] == 29
