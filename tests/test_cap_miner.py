import unittest

from src.cap_miner import (
    forge_extract,
    implementation_status,
    java_extract,
    norm,
    select_unambiguous,
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


if __name__ == "__main__":
    unittest.main()
