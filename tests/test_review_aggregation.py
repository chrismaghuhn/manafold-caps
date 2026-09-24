import unittest

from src.review_aggregation import (
    build_adjudications,
    finalize_primary_decisions,
    nominal_agreement,
    pattern_aggs,
    split_packet_samples,
    validate_review_subset,
)


class ReviewAggregationTest(unittest.TestCase):
    def test_reviewer_b_subset_validation_is_exact(self):
        result=validate_review_subset({"a","b","c"},{"a","b"},2)
        self.assertTrue(result["subset_valid"])
        broken=validate_review_subset({"a","b"},{"a","c"},2)
        self.assertFalse(broken["subset_valid"])
        self.assertEqual(broken["missing_from_a"],["c"])

    def test_agreement_metrics_match_degenerate_marginal_fixture(self):
        a=["CORRECT"]*208
        b=["CORRECT"]*204+["WRONG"]*4
        result=nominal_agreement(a,b)
        self.assertEqual(result["n"],208)
        self.assertAlmostEqual(result["raw_agreement"],204/208)
        self.assertAlmostEqual(result["cohen_kappa"],0.0,places=12)
        self.assertAlmostEqual(result["gwet_ac1"],0.9803958529688972,places=10)
        self.assertTrue(result["single_category_reviewer_a_marginal_warning"])

    def test_forced_audit_is_split_from_primary_sample(self):
        primary,forced=split_packet_samples([
            {"sample_id":"p","selection_basis":"PROBABILITY_SAMPLE"},
            {"sample_id":"f","selection_basis":"FORCED_FLAGGED_JOIN_AUDIT"},
        ])
        self.assertEqual([r["sample_id"] for r in primary],["p"])
        self.assertEqual([r["sample_id"] for r in forced],["f"])

    def test_adjudication_consumes_all_four_supplied_disagreements(self):
        ids=["053d9fe47d105986611506c8","80e88eda5a088379b9af218a","23a6562a6e6a5c5879b55310","532892f8dc083b10a99ec57d"]
        disputes={"disagreements":[{"sample_id":sid,"card_name":"sample","pattern_id":"forge.change_zone.v1","reviewer_a":"CORRECT","reviewer_b":"WRONG","recommended_resolution":"WRONG"} for sid in ids]}
        samples={sid:{"evidence":{"forge":{"selected_constructs":["ChangeZone"],"source_record_identity":sid,"parameters":{"Origin":["Library"],"Destination":["Library"]}}}} for sid in ids}
        result,issues=build_adjudications(disputes,samples)
        self.assertEqual(len(result),4)
        self.assertEqual(issues,[])
        self.assertEqual({r["final_label"] for r in result},{"WRONG"})

    def test_final_primary_counts_after_four_wrong_adjudications(self):
        ids=[f"sample-{i:03d}" for i in range(460)]
        a={sid:("WRONG" if i==459 else "CORRECT") for i,sid in enumerate(ids)}
        disagreements=ids[:4]
        b={sid:("WRONG" if sid in disagreements else a[sid]) for sid in ids[:208]}
        adjudications=[{"sample_id":sid,"final_label":"WRONG"} for sid in disagreements]
        final,counts=finalize_primary_decisions(a,b,adjudications)
        self.assertEqual(len(final),460)
        self.assertEqual(counts["CORRECT"],455)
        self.assertEqual(counts["WRONG"],5)
        self.assertEqual(sum(counts.values()),460)

    def test_pattern_counts_are_decisive_and_do_not_create_requirement_precision(self):
        ids=["a","b","c","d"]
        decisions={"a":"CORRECT","b":"WRONG","c":"AMBIGUOUS","d":"SOURCE_EVIDENCE_INSUFFICIENT"}
        pattern_inventory={"patterns":[{"pattern_id":"forge.destroy.v1","population_size":10,"probability_sample_size":4,"probability_sample_ids":ids}]}
        first=pattern_aggs(decisions,[],pattern_inventory)
        second=pattern_aggs(decisions,[],pattern_inventory)
        self.assertEqual(first,second)
        self.assertEqual(first[0]["decisive_n"],2)
        self.assertEqual(first[0]["precision_estimate"],0.5)
        self.assertEqual(sum(first[0]["counts"].values()),4)
        self.assertNotIn("requirement_precision",first[0])


if __name__ == "__main__":
    unittest.main()
