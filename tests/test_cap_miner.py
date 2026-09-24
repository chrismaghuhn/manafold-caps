import unittest

from src.cap_miner import (
    forge_extract,
    implementation_status,
    java_extract,
    mismatch_diagnostic,
    norm,
    oracle_text,
    partition_tokens,
    resolution_bucket,
    select_unambiguous,
    summarize_card_resolution,
    xmage_semantic_classes,
)


class MinerHelpersTest(unittest.TestCase):
    def test_normalization_is_deterministic_and_unicode_safe(self):
        self.assertEqual(norm("  Æther—Äbeyance "), norm("Æther Äbeyance"))
        self.assertEqual(norm("A\u0308"), norm("Ä"))

    def test_ambiguous_exact_candidates_are_not_selected(self):
        self.assertEqual(select_unambiguous(["oracle-a", "oracle-a"]), "oracle-a")
        self.assertIsNone(select_unambiguous(["oracle-a", "oracle-b"]))

    def test_forge_extracts_open_ended_action_and_fields(self):
        actions, attributes, snippets = forge_extract(
            r"A:SP$ ChangeZone | Origin$ Graveyard | Destination$ Battlefield | ValidTgts$ Permanent.YouCtrl\n"
            r"SVar:DBDamage:DB$ Damage | NumDmg$ 2"
        )
        self.assertEqual(actions, ["ChangeZone", "Damage"])
        self.assertIn("Origin", attributes)
        self.assertIn("Destination", attributes)
        self.assertTrue(snippets)

    def test_xmage_import_and_constructor_vocabulary(self):
        imports, classes, snippet = java_extract(
            "import mage.abilities.effects.common.DamageTargetEffect;\n"
            "new SimpleActivatedAbility( new DamageTargetEffect(2) );"
        )
        self.assertIn("mage.abilities.effects.common.DamageTargetEffect", imports)
        self.assertIn("DamageTargetEffect", classes)
        self.assertIn("SimpleActivatedAbility", classes)
        self.assertIn("DamageTargetEffect", snippet)

    def test_implementation_agreement_is_not_authority(self):
        self.assertEqual(implementation_status({"forge", "xmage"}), "MULTI_IMPLEMENTATION_AGREEMENT")
        self.assertEqual(implementation_status({"forge"}), "FORGE_ONLY")
        self.assertEqual(implementation_status({"xmage"}), "XMAGE_ONLY")
        self.assertEqual(implementation_status(["xmage", "forge"]), implementation_status(["forge", "xmage"]))

    def test_card_resolution_counts_identities_not_requirement_rows(self):
        result=summarize_card_resolution(2,{0},{0},{0},{0})
        self.assertEqual(result["with_any_mapped_requirement"],1)
        self.assertEqual(result["with_both_evidence"],1)
        self.assertEqual(result["partially_resolved"],1)
        self.assertEqual(result["fully_resolved"],0)

    def test_resolution_buckets_retain_unmapped_evidence(self):
        self.assertEqual(resolution_bucket(True,0,3),"FULLY_UNRESOLVED")
        self.assertEqual(resolution_bucket(True,2,1),"PARTIALLY_RESOLVED")
        self.assertEqual(resolution_bucket(True,1,0),"COMPLETENESS_UNVERIFIED")
        mapped,unmapped=partition_tokens("forge",["DealDamage","ChangesZone"],{"DealDamage":"damage"},"normalized_name",4)
        self.assertEqual(mapped["damage"][0]["token"],"DealDamage")
        self.assertEqual(unmapped,[{"source":"forge","token":"ChangesZone","match_method":"normalized_name","source_record_index":4}])

    def test_oracle_mismatch_classifier_is_deterministic_and_template_aware(self):
        card={"name":"Static Orb","type_line":"Artifact","oracle_text":"As long as this artifact is untapped, players can't untap more than two permanents during their untap steps.","card_faces":[]}
        record={"input":"{\"name\":\"Static Orb\",\"oracle_text\":\"As long as Static Orb is untapped, players can't untap more than two permanents during their untap steps.\"}"}
        self.assertEqual(mismatch_diagnostic("forge",record,card),mismatch_diagnostic("forge",record,card))
        self.assertEqual(mismatch_diagnostic("forge",record,card)["category"],"EXACT_AFTER_CARDNAME_TEMPLATE_NORMALIZATION")

    def test_xmage_prompt_extracts_all_faces_without_following_metadata(self):
        prompt="Name: A // B\nOracle Text: Front face text.\nName: B\nMana Cost: {U}\nOracle Text: Back face text.\nColors: U\nRarity: rare"
        self.assertEqual(oracle_text({"prompt":prompt}),"Front face text.\nBack face text.")

    def test_exact_name_matching_never_uses_fuzzy_candidates_as_authority(self):
        self.assertNotEqual(norm("Abrade"),norm("Abras"))
        self.assertIsNone(select_unambiguous([]))
        self.assertIsNone(select_unambiguous(["Abrade","Abras"]))

    def test_action_and_event_tokens_remain_distinct(self):
        from src.cap_miner import read_mapping
        mapping=read_mapping()
        self.assertEqual(mapping["forge"]["DealDamage"],"damage")
        self.assertEqual(mapping["forge"]["ChangeZone"],"zone_transition")
        self.assertNotIn("ChangesZone",mapping["forge"])

    def test_broad_xmage_framework_classes_are_excluded(self):
        self.assertEqual(xmage_semantic_classes(["OneShotEffect","SimpleActivatedAbility","TargetPermanent","FilterPermanent"]),[])
        self.assertEqual(xmage_semantic_classes(["DamageTargetEffect"]),["DamageTargetEffect"])


if __name__ == "__main__":
    unittest.main()
