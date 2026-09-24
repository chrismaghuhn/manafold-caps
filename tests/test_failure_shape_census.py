import unittest

from src.failure_shape_census import _sample_guard_impact, classify_java_class_usage, forge_zone_occurrences


class FailureShapeCensusTest(unittest.TestCase):
    def test_forge_same_and_cross_zone_occurrences(self):
        record = {"output": "A:DB$ ChangeZone | Origin$ Library | Destination$ Exile\n:DB$ ChangeZoneAll | Origin$ Library | Destination$ Library"}
        occurrences = forge_zone_occurrences(record, "forge@rev:row:00000001")
        self.assertEqual([row["classification"] for row in occurrences], ["CROSS_ZONE", "SAME_ZONE"])

    def test_forge_multivalued_and_missing_endpoints_are_not_guessed(self):
        record = {"output": "A:DB$ ChangeZone | Origin$ Library,Hand | Destination$ Library\n:DB$ ChangeZoneAll | Destination$ Graveyard\n:DB$ ChangeZone | Origin$ Library"}
        occurrences = forge_zone_occurrences(record, "forge@rev:row:00000002")
        self.assertEqual([row["classification"] for row in occurrences], ["ORIGIN_OR_DESTINATION_MULTI_VALUED", "ORIGIN_MISSING", "DESTINATION_MISSING"])

    def test_xmage_import_only_and_constructor_usage(self):
        imported = "import mage.abilities.effects.common.DestroyTargetEffect;\npublic class X { }"
        used = imported + "\nvoid f() { new DestroyTargetEffect(); }"
        self.assertEqual(classify_java_class_usage(imported, "DestroyTargetEffect")["classification"], "IMPORTED_ONLY")
        self.assertEqual(classify_java_class_usage(used, "DestroyTargetEffect")["classification"], "INSTANTIATED")

    def test_comments_and_strings_do_not_count_as_executable_use(self):
        comment = "// new DestroyTargetEffect()\nclass X {}"
        literal = 'class X { String s = "new DestroyTargetEffect()"; }'
        self.assertEqual(classify_java_class_usage(comment, "DestroyTargetEffect")["classification"], "UNRESOLVED_USAGE")
        self.assertTrue(classify_java_class_usage(comment, "DestroyTargetEffect")["comment_or_string_only"])
        self.assertEqual(classify_java_class_usage(comment, "DestroyTargetEffect")["comment_mentions"], 1)
        self.assertEqual(classify_java_class_usage(literal, "DestroyTargetEffect")["classification"], "UNRESOLVED_USAGE")
        self.assertTrue(classify_java_class_usage(literal, "DestroyTargetEffect")["comment_or_string_only"])
        self.assertEqual(classify_java_class_usage(literal, "DestroyTargetEffect")["string_literal_mentions"], 1)

    def test_fully_qualified_constructor_is_instantiated(self):
        source = "class X { void f() { new mage.abilities.effects.common.DestroyTargetEffect(); } }"
        self.assertEqual(classify_java_class_usage(source, "DestroyTargetEffect")["classification"], "INSTANTIATED")

    def test_review_impact_is_pattern_and_construct_specific(self):
        samples = [
            {"sample_id": "same", "pattern_id": "forge.change_zone.v1", "pattern": {"source": "forge", "external_construct": "ChangeZone"}, "evidence": {"forge": {"source_record_identity": "row1"}}, "card": {"name": "A"}},
            {"sample_id": "cross", "pattern_id": "cross.create_token.v1", "pattern": {"source": "cross", "external_constructs": [{"source": "forge", "token": "Token"}]}, "evidence": {"forge": {"source_record_identity": "row1"}}, "card": {"name": "A"}},
        ]
        result = _sample_guard_impact(samples, {"same": "WRONG", "cross": "CORRECT"}, {("forge", "row1", "ChangeZone")}, "forge")
        self.assertEqual(result["samples_changed"], 1)
        self.assertEqual(result["WRONG"], 1)
        self.assertEqual(result["CORRECT"], 0)


if __name__ == "__main__":
    unittest.main()
