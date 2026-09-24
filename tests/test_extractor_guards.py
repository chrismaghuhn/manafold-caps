import unittest

from src.cap_miner import (
    classify_java_class_usage,
    forge_guard_filter,
    partition_tokens,
    xmage_guard_filter,
)
from src.guard_differential import candidate_occurrences, reviewed_sample_regression


class ExtractorGuardTest(unittest.TestCase):
    def test_forge_same_zone_actions_suppressed_and_cross_zone_preserved(self):
        for action in ("ChangeZone", "ChangeZoneAll"):
            record = {"output": f":DB$ {action} | Origin$ Library | Destination$ Library"}
            eligible, indices, suppressed = forge_guard_filter(record, [action])
            self.assertEqual(eligible, [])
            self.assertEqual(indices, [])
            self.assertEqual(len(suppressed), 1)
        for origin, destination in (("Library", "Exile"), ("Graveyard", "Battlefield")):
            record = {"output": f":DB$ ChangeZone | Origin$ {origin} | Destination$ {destination}"}
            eligible, indices, suppressed = forge_guard_filter(record, ["ChangeZone"])
            self.assertEqual(eligible, ["ChangeZone"])
            self.assertEqual(indices, [0])
            self.assertEqual(suppressed, [])

    def test_forge_missing_or_multivalued_zones_are_preserved(self):
        record = {"output": "\n".join([
            ":DB$ ChangeZone | Destination$ Library",
            ":DB$ ChangeZone | Origin$ Library",
            ":DB$ ChangeZone | Origin$ Library,Hand | Destination$ Library",
            ":DB$ ChangeZone | Origin$ Any | Destination$ Any",
        ])}
        eligible, indices, suppressed = forge_guard_filter(record, ["ChangeZone"] * 4)
        self.assertEqual(eligible, ["ChangeZone"] * 4)
        self.assertEqual(indices, [0, 1, 2, 3])
        self.assertEqual(suppressed, [])

    def test_forge_mixed_hew_the_entwood_shape_filters_only_same_zone_occurrence(self):
        record = {"output": "\n".join([
            ":DB$ ChangeZoneAll | ChangeType$ Artifact.ChosenCard | Origin$ Library | Destination$ Battlefield | SubAbility$ DBPutLands",
            ":DB$ ChangeZoneAll | ChangeType$ Land.ChosenCard | Origin$ Library | Destination$ Battlefield | Tapped$ True | SubAbility$ ShuffleRest",
            ":DB$ ChangeZoneAll | Origin$ Library | Destination$ Library | LibraryPosition$ -1 | RandomOrder$ True | ChangeType$ Card.IsRemembered+!ChosenCard | SubAbility$ DBCleanup",
        ])}
        eligible, indices, suppressed = forge_guard_filter(record, ["ChangeZoneAll"] * 3)
        self.assertEqual(eligible, ["ChangeZoneAll", "ChangeZoneAll"])
        self.assertEqual(indices, [0, 1])
        self.assertEqual(len(suppressed), 1)
        self.assertEqual(suppressed[0]["occurrence_index"], 2)
        mapped, _ = partition_tokens("forge", eligible, {"ChangeZoneAll": "zone_transition"}, occurrence_indices=indices, include_occurrence_index=True)
        self.assertEqual([r["occurrence_index"] for r in mapped["zone_transition"]], [0, 1])

    def test_xmage_import_only_is_suppressed_but_constructor_and_executable_use_remain(self):
        mapping = {"DestroyTargetEffect": "destroy", "CreateTokenEffect": "create_token"}
        import_only = "import mage.abilities.effects.common.DestroyTargetEffect; class A {}"
        java = "import mage.abilities.effects.common.DestroyTargetEffect; class A { void f() { new DestroyTargetEffect(); } }"
        eligible, suppressed = xmage_guard_filter(import_only, ["DestroyTargetEffect"], mapping)
        self.assertEqual(eligible, [])
        self.assertEqual([r["token"] for r in suppressed], ["DestroyTargetEffect"])
        eligible, suppressed = xmage_guard_filter(java, ["DestroyTargetEffect"], mapping)
        self.assertEqual(eligible, ["DestroyTargetEffect"])
        self.assertEqual(suppressed, [])

    def test_xmage_non_executable_mentions_do_not_count_as_use(self):
        comment = "import mage.abilities.effects.common.DestroyTargetEffect; // new DestroyTargetEffect()"
        literal = 'import mage.abilities.effects.common.DestroyTargetEffect; class A { String x = "DestroyTargetEffect()"; }'
        for source in (comment, literal):
            eligible, suppressed = xmage_guard_filter(source, ["DestroyTargetEffect"], {"DestroyTargetEffect": "destroy"})
            self.assertEqual(eligible, [])
            self.assertEqual(suppressed[0]["usage"]["classification"], "IMPORTED_ONLY")
        self.assertEqual(classify_java_class_usage("// new DestroyTargetEffect()", "DestroyTargetEffect")["classification"], "UNRESOLVED_USAGE")
        comment_only, _ = xmage_guard_filter("// new DestroyTargetEffect()", ["DestroyTargetEffect"], {"DestroyTargetEffect": "destroy"})
        string_only, _ = xmage_guard_filter('class A { String x = "DestroyTargetEffect()"; }', ["DestroyTargetEffect"], {"DestroyTargetEffect": "destroy"})
        self.assertEqual(comment_only, [])
        self.assertEqual(string_only, [])

    def test_xmage_fully_qualified_constructor_and_other_executable_reference_remain(self):
        fqcn = "class A { void f() { new mage.abilities.effects.common.DestroyTargetEffect(); } }"
        method = "import mage.abilities.effects.common.DestroyTargetEffect; class A { void f() { DestroyTargetEffect.copy(); } }"
        self.assertEqual(xmage_guard_filter(fqcn, ["DestroyTargetEffect"], {"DestroyTargetEffect": "destroy"})[0], ["DestroyTargetEffect"])
        self.assertEqual(classify_java_class_usage(method, "DestroyTargetEffect")["classification"], "USED_OTHER_EXECUTABLE_CONTEXT")
        self.assertEqual(xmage_guard_filter(method, ["DestroyTargetEffect"], {"DestroyTargetEffect": "destroy"})[0], ["DestroyTargetEffect"])

    def test_xmage_multiple_classes_suppresses_only_import_only_class(self):
        source = "import mage.effects.ImportedOnly; import mage.effects.RealEffect; class A { void f() { new RealEffect(); } }"
        eligible, suppressed = xmage_guard_filter(source, ["ImportedOnly", "RealEffect"], {"ImportedOnly": "a", "RealEffect": "b"})
        self.assertEqual(eligible, ["RealEffect"])
        self.assertEqual([r["token"] for r in suppressed], ["ImportedOnly"])

    def test_differential_identity_keeps_occurrence_ordinals_stable(self):
        baseline = [{"oracle_id": "oid", "name": "mixed", "requirements": [{"kind": "zone_transition", "evidence": [
            {"source": "forge", "token": "ChangeZoneAll", "source_record_index": 8},
            {"source": "forge", "token": "ChangeZoneAll", "source_record_index": 8},
        ]}]}]
        old = candidate_occurrences(baseline, old_format=True)
        self.assertEqual({key[-1] for key in old}, {0, 1})
        new_row = [{"oracle_id": "oid", "name": "mixed", "requirements": [{"kind": "zone_transition", "evidence": [
            {"source": "forge", "token": "ChangeZoneAll", "source_record_index": 8, "occurrence_index": 1},
        ]}]}]
        new = candidate_occurrences(new_row)
        self.assertEqual(set(new), {key for key in old if key[-1] == 1})

    def test_review_regression_counts_candidate_path_loss_not_any_record_filter(self):
        samples = [
            {"sample_id": "mixed", "selection_basis": "PROBABILITY_SAMPLE", "pattern_id": "forge.change_zone_all.v1", "pattern": {"source": "forge", "external_construct": "ChangeZoneAll", "proposed_requirement": "zone_transition"}, "card": {"oracle_id": "mixed", "name": "Mixed"}, "evidence": {"forge": {"source_record_identity": "forge-row"}}},
            {"sample_id": "false", "selection_basis": "PROBABILITY_SAMPLE", "pattern_id": "forge.change_zone.v1", "pattern": {"source": "forge", "external_construct": "ChangeZone", "proposed_requirement": "zone_transition"}, "card": {"oracle_id": "false", "name": "False"}, "evidence": {"forge": {"source_record_identity": "forge-row-2"}}},
        ]
        old = {
            ("mixed", "forge", "forge-row", "ChangeZoneAll", "zone_transition", 0): {},
            ("mixed", "forge", "forge-row", "ChangeZoneAll", "zone_transition", 1): {},
            ("false", "forge", "forge-row-2", "ChangeZone", "zone_transition", 0): {},
        }
        new = {key: {} for key in old if key[-1] == 1 and key[0] == "mixed"}
        result = reviewed_sample_regression(samples, {"mixed": "CORRECT", "false": "WRONG"}, old, new)
        self.assertEqual(result["samples_removed"], 1)
        self.assertEqual(result["CORRECT_removed"], 0)
        self.assertEqual(result["WRONG_removed"], 1)


if __name__ == "__main__":
    unittest.main()
