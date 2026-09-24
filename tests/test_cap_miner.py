import unittest

from src.cap_miner import (
    forge_extract,
    forge_parameter_inventory,
    implementation_status,
    java_review_excerpt,
    apply_join_review,
    can_reserve_sample_occurrences,
    canonical_oracle_info,
    deterministic_sample_id,
    empty_interval_for_population,
    exact_oracle_id_match,
    hypergeometric_interval,
    interval_method_for_population,
    java_extract,
    load_join_decisions,
    join_review_metadata,
    lookup_join_decision,
    stable_second_review_ids,
    source_text_status_by_engine,
    stratified_stable_sample,
    validation_status_from_results,
    validate_review_decision,
    wilson_interval,
    mismatch_diagnostic,
    norm,
    oracle_text,
    partition_tokens,
    resolution_bucket,
    sample_id_set_sha256,
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

    def test_reviewed_reject_is_excluded_and_kept_join_stays_eligible(self):
        rejected={"action":"REJECT_JOIN","result":"BAD_JOIN_NAME_COLLISION","reason":"two exact names collide"}
        kept={"action":"KEEP_JOIN","result":"VALID_JOIN_STALE_WORDING","reason":"historical text"}
        self.assertEqual(apply_join_review(12,rejected),(False,None))
        self.assertEqual(apply_join_review(12,kept),(True,{"join_review_status":"KEEP_JOIN","join_review_result":"VALID_JOIN_STALE_WORDING","join_review_reason":"historical text"}))

    def test_flagged_join_retains_warning_metadata(self):
        decision={"action":"KEEP_WITH_FLAG","result":"SOURCE_RECORD_WRONG_OR_CORRUPT","reason":"prompt type dash is mojibake"}
        allowed,metadata=apply_join_review(3,decision)
        self.assertTrue(allowed)
        self.assertEqual(metadata["join_review_status"],"KEEP_WITH_FLAG")
        self.assertEqual(metadata["join_review_reason"],"prompt type dash is mojibake")

    def test_review_lookup_is_deterministic(self):
        decisions=load_join_decisions()
        aid="xmage:1b6e0d65-202e-4fd3-861e-8d2eaffe3269"
        self.assertEqual(len(decisions),58)
        self.assertEqual(lookup_join_decision(decisions,aid),lookup_join_decision(decisions,aid))
        self.assertEqual(decisions[aid]["action"],"KEEP_WITH_FLAG")

    def test_oracle_id_precedes_name_or_text_similarity(self):
        self.assertEqual(exact_oracle_id_match({"oracle_id":"oracle-exact","name":"Near Match"},{"oracle-exact":[7]}),(7,"oracle_id"))
        self.assertIsNone(exact_oracle_id_match({"oracle_id":"near-match","name":"Exact Name"},{"other-id":[2]}))

    def test_pattern_ids_and_stratified_selection_are_deterministic(self):
        self.assertEqual(deterministic_sample_id("forge.draw.v1","oid","forge@rev:row:1"),deterministic_sample_id("forge.draw.v1","oid","forge@rev:row:1"))
        candidates=[{"sample_id":f"id-{i:02d}","stratum":{"type":"creature" if i%2 else "land","face":"single"}} for i in range(8)]
        self.assertEqual(stratified_stable_sample(candidates,5),stratified_stable_sample(candidates,5))

    def test_source_occurrence_is_not_reused(self):
        used={"forge@revision:row:00000001"}
        self.assertFalse(can_reserve_sample_occurrences("forge@revision:row:00000001|xmage@revision:row:00000002",used))
        self.assertTrue(can_reserve_sample_occurrences("forge@revision:row:00000003",used))

    def test_high_risk_second_review_and_medium_sample(self):
        samples=[{"sample_id":f"s{i:02d}"} for i in range(40)]
        self.assertEqual(len(stable_second_review_ids(samples,"HIGH",1.0)),40)
        self.assertEqual(len(stable_second_review_ids(samples,"MEDIUM",0.2)),8)

    def test_review_enum_and_no_results_state(self):
        self.assertEqual(validate_review_decision("CORRECT"),"CORRECT")
        with self.assertRaises(ValueError): validate_review_decision("MAYBE")
        self.assertEqual(validation_status_from_results([]),"AWAITING_REVIEW")

    def test_wilson_interval_known_values(self):
        interval=wilson_interval(5,10)
        self.assertAlmostEqual(interval["estimate"],0.5)
        self.assertAlmostEqual(interval["lower"],0.2366,places=3)
        self.assertAlmostEqual(interval["upper"],0.7634,places=3)
        self.assertIsNone(wilson_interval(0,0)["lower"])

    def test_finite_population_method_and_hypergeometric_bounds(self):
        self.assertAlmostEqual(40/4136,0.00967,places=4)
        self.assertEqual(interval_method_for_population(4136,40),"WILSON_BINOMIAL")
        self.assertEqual(interval_method_for_population(117,40),"FINITE_POPULATION_HYPERGEOMETRIC")
        interval=hypergeometric_interval(100,20,10)
        self.assertGreaterEqual(interval["lower"],0.0)
        self.assertLessEqual(interval["upper"],1.0)
        self.assertLessEqual(interval["lower"],interval["estimate"])
        self.assertGreaterEqual(interval["upper"],interval["estimate"])
        self.assertEqual(interval,hypergeometric_interval(100,20,10))

    def test_hypergeometric_census_has_no_sampling_uncertainty(self):
        interval=hypergeometric_interval(10,10,4)
        self.assertEqual(interval["lower"],0.4)
        self.assertEqual(interval["upper"],0.4)

    def test_missing_source_text_does_not_hide_canonical_face_text(self):
        canonical=canonical_oracle_info({"oracle_text":None,"card_faces":[{"name":"Front","oracle_text":"Front text."},{"name":"Back","oracle_text":"Back text."}]})
        self.assertEqual(canonical["status"],"FACE_TEXT_AVAILABLE")
        statuses=source_text_status_by_engine({"forge":{"present":True,"source_oracle_text":""},"xmage":{"present":False}})
        self.assertEqual(statuses["forge"],"MISSING")
        self.assertTrue(canonical["status"]!="MISSING")

    def test_existing_probability_sample_ids_match_phase_0_2a_baseline_when_packet_exists(self):
        import json
        from pathlib import Path
        from src.cap_miner import sample_id_set_sha256
        path=Path(__file__).resolve().parents[1]/"data"/"output"/"review_samples.jsonl"
        if not path.exists(): self.skipTest("Generated Phase 0.2A review packet is not present yet")
        rows=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        primary=[r for r in rows if r.get("selection_basis","PROBABILITY_SAMPLE")=="PROBABILITY_SAMPLE"]
        low=[r for r in primary if r["pattern"]["risk"]=="LOW"]
        self.assertEqual(len(primary),460)
        self.assertEqual(len(low),60)
        self.assertEqual(sample_id_set_sha256(primary),"feeb4a19ef205df5cb61078e2df8f1ba11f4570b548ac238bd84f59447e93faf")
        self.assertEqual(sample_id_set_sha256(low),"7423edb900b12bbd86242937da295ea66833c0b4dbcafce1c643917c260eac31")

    def test_forced_warning_sample_is_separate_from_probability_sizes_when_packet_exists(self):
        import json
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        path=root/"data"/"output"/"review_samples.jsonl"
        if not path.exists(): self.skipTest("Generated review packet is not present yet")
        rows=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not rows or "selection_basis" not in rows[0]: self.skipTest("Review packet has not been regenerated for Phase 0.2A.1")
        primary=[r for r in rows if r["selection_basis"]=="PROBABILITY_SAMPLE"]
        forced=[r for r in rows if r["selection_basis"]=="FORCED_FLAGGED_JOIN_AUDIT"]
        inventory=json.loads((root/"data"/"output"/"pattern_inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(len(primary),460)
        self.assertEqual(len(forced),1)
        self.assertEqual(inventory["total_samples"],460)
        self.assertEqual(inventory["total_review_packet_items"],461)
        self.assertTrue(forced[0]["known_join_warning"])
        self.assertFalse(forced[0]["covered_by_probability_sample"])

    def test_plan_keeps_mapping_hash_at_phase_0_1_2_value(self):
        import hashlib
        from pathlib import Path
        digest=hashlib.sha256((Path(__file__).resolve().parents[1]/"mappings.yaml").read_bytes()).hexdigest()
        self.assertEqual(digest,"3f087dd50b5d927e90ca7d979586d0aa358fb75b74c856fffcac79ab1389ca8a")

    def test_validation_plan_is_bounded_and_zone_patterns_keep_context_fields(self):
        import yaml
        from pathlib import Path
        text=(Path(__file__).resolve().parents[1]/"validation_plan.yaml").read_text(encoding="utf-8")
        self.assertEqual(text.count("interval_method_threshold:"),1)
        self.assertEqual(text.count("interval_method_policy:"),1)
        plan=yaml.safe_load(text)
        self.assertEqual(len(plan["patterns"]),15)
        self.assertLessEqual(sum(p["sample_size"] for p in plan["patterns"]),500)
        self.assertEqual(plan["sampling"]["interval_method_threshold"],0.05)
        zone=next(p for p in plan["patterns"] if p["pattern_id"]=="forge.change_zone.v1")
        self.assertTrue({"Origin","Destination","ValidTgts","ChangeType","ChangeNum"}.issubset(zone["context_fields"]))

    def test_high_risk_forge_parameters_are_retained(self):
        params=forge_parameter_inventory({"output":"A:SP$ ChangeZone | Origin$ Graveyard | Destination$ Battlefield | ValidTgts$ Creature.YouCtrl | ChangeNum$ 1"})
        self.assertEqual(params["Origin"],["Graveyard"])
        self.assertEqual(params["Destination"],["Battlefield"])
        self.assertEqual(params["ValidTgts"],["Creature.YouCtrl"])
        self.assertEqual(params["ChangeNum"],["1"])

    def test_xmage_review_excerpt_keeps_effect_construction_context(self):
        excerpt=java_review_excerpt("import mage.abilities.effects.common.ExileTargetEffect;\n"
                                   "Ability ability = new SimpleActivatedAbility(cost);\n"
                                   "ability.addEffect(new ExileTargetEffect(filter));\n",{"ExileTargetEffect"})
        self.assertIn("ExileTargetEffect(filter)",excerpt)

    def test_join_warning_is_carried_into_review_metadata(self):
        metadata=join_review_metadata("xmage","1b6e0d65-202e-4fd3-861e-8d2eaffe3269",load_join_decisions())
        self.assertEqual(metadata["join_review_status"],"KEEP_WITH_FLAG")
        self.assertIn("mojibake",metadata["join_review_reason"])


if __name__ == "__main__":
    unittest.main()
