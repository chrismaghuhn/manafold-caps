import unittest

from src.differential_review_packet import (
    _sample_id,
    build_forge_review_item,
    build_xmage_review_item,
    forge_action_occurrences,
    java_reference_contexts,
    validate_review_decision,
)


class DifferentialReviewPacketTest(unittest.TestCase):
    def test_differential_sample_id_is_stable_and_guard_bound(self):
        identity = {"oracle_id": "oid", "source": "forge", "source_record_identity": "forge@rev:row:1", "external_construct": "ChangeZone", "requirement": "zone_transition", "occurrence_index": 2}
        self.assertEqual(_sample_id("FORGE_SAME_ZONE", identity), _sample_id("FORGE_SAME_ZONE", identity))
        self.assertNotEqual(_sample_id("FORGE_SAME_ZONE", identity), _sample_id("XMAGE_IMPORT_ONLY", identity))

    def test_forge_item_points_to_exact_action_and_preserves_sibling_actions(self):
        source = {"output": "\n".join([
            ":DB$ ChangeZoneAll | Origin$ Library | Destination$ Battlefield | ChangeType$ Land.ChosenCard",
            ":DB$ ChangeZoneAll | Origin$ Library | Destination$ Library | LibraryPosition$ -1 | RandomOrder$ True",
        ])}
        actions = forge_action_occurrences(source)
        removed = {"oracle_id": "oid", "source": "forge", "source_record_identity": "forge@rev:row:1", "external_construct": "ChangeZoneAll", "requirement": "zone_transition", "occurrence_index": 1, "card_name": "Mixed"}
        card = {"oracle_id": "oid", "name": "Mixed", "type_line": "Sorcery", "layout": "normal", "oracle_text": "text", "card_faces": []}
        item = build_forge_review_item(removed, card, source, actions)
        self.assertEqual(item["evidence"]["action_occurrence_index"], 1)
        self.assertEqual(item["evidence"]["action_local_parameters"]["Destination"], ["Library"])
        self.assertEqual([a["is_removed_occurrence"] for a in item["evidence"]["source_record_action_lines"]], [False, True])

    def test_xmage_packet_shows_all_reference_contexts_and_keeps_raw_java(self):
        source = "import mage.effects.DestroyTargetEffect;\nclass A { // DestroyTargetEffect was considered\n String x = \"DestroyTargetEffect\";\n}"
        contexts = java_reference_contexts(source, "DestroyTargetEffect")
        self.assertEqual({row["context"] for row in contexts}, {"IMPORT", "COMMENT", "STRING_OR_CHAR_LITERAL"})
        removed = {"oracle_id": "oid", "source": "xmage", "source_record_identity": "xmage@rev:row:2", "external_construct": "DestroyTargetEffect", "requirement": "destroy", "occurrence_index": 0, "card_name": "A"}
        card = {"oracle_id": "oid", "name": "A", "type_line": "Creature", "layout": "normal", "oracle_text": "destroy", "card_faces": []}
        usage = {"classification": "IMPORTED_ONLY", "executable_mentions": 0, "import_paths": ["mage.effects.DestroyTargetEffect"], "comment_mentions": 1, "string_literal_mentions": 1, "package_mentions": 0}
        item = build_xmage_review_item(removed, card, {"completion": source}, usage)
        self.assertEqual(item["evidence"]["source_java"], source)
        self.assertEqual(item["evidence"]["executable_context_excerpt"], "")
        self.assertEqual(len(item["evidence"]["all_class_name_references"]), 3)

    def test_result_enum_rejects_unknown_values(self):
        self.assertEqual(validate_review_decision("REMOVAL_CORRECT"), "REMOVAL_CORRECT")
        with self.assertRaises(ValueError):
            validate_review_decision("CORRECT")


if __name__ == "__main__":
    unittest.main()
