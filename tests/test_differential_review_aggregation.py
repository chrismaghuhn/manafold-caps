import hashlib
import json
import unittest

from src.differential_review_aggregation import (
    pattern_transfer,
    summarize_reviewers,
    validate_unchanged_identity,
)


class DifferentialReviewAggregationTest(unittest.TestCase):
    def setUp(self):
        self.ids=[f"differential:{n:024x}" for n in range(104)]

    def test_104_exact_reviewer_agreement_is_not_reported_as_kappa_one(self):
        a={sid:{"decision":"REMOVAL_CORRECT"} for sid in self.ids}
        b={sid:{"decision":"REMOVAL_CORRECT"} for sid in self.ids}
        result=summarize_reviewers(a,b,set(self.ids))
        self.assertEqual(sum(result["reviewer_a_counts"].values()),104)
        self.assertEqual(sum(result["reviewer_b_counts"].values()),104)
        self.assertEqual(result["agreement"]["exact_agreement"],104)
        self.assertEqual(result["agreement"]["disagreements"],0)
        self.assertEqual(result["agreement"]["raw_agreement"],1.0)
        self.assertEqual(result["agreement"]["cohen_kappa"],"NOT_INFORMATIVE_SINGLE_CATEGORY")
        self.assertEqual(result["agreement"]["gwet_ac1"],"NOT_INFORMATIVE_SINGLE_CATEGORY")

    def test_id_sets_must_exactly_match_packet(self):
        a={sid:{"decision":"REMOVAL_CORRECT"} for sid in self.ids}
        b=dict(a);b.pop(self.ids[-1]);b["unexpected"]={"decision":"REMOVAL_CORRECT"}
        with self.assertRaises(ValueError): summarize_reviewers(a,b,set(self.ids))

    def test_unchanged_identity_digest_and_added_zero_are_required(self):
        old={("a",), ("b",)};new={("b",)}
        payload=json.dumps(["b"],separators=(",",":"))
        digest=hashlib.sha256(payload.encode()).hexdigest()
        proof=validate_unchanged_identity(old,new,digest)
        self.assertTrue(proof["match"])
        self.assertEqual(proof["removed"],1)
        with self.assertRaises(ValueError): validate_unchanged_identity(old,new,"bad")
        with self.assertRaises(ValueError): validate_unchanged_identity(old,{("a",),("b",),("c",)},digest)

    def test_pattern_transfer_labels_unchanged_and_removals_only_without_precision(self):
        evidence={"source":"forge","token":"ChangeZone","source_record_index":2,"occurrence_index":0}
        old=[{"oracle_id":"one","requirements":[{"kind":"zone_transition","evidence":[evidence]}]}]
        new=[{"oracle_id":"one","requirements":[]}]
        inventory={"patterns":[{"pattern_id":"forge.change_zone.v1","population_size":1,"source":"forge","external_construct":"ChangeZone","proposed_requirement":"zone_transition"}]}
        diff={"removed_occurrences":[{"oracle_id":"one","source":"forge","external_construct":"ChangeZone","requirement":"zone_transition"}]}
        result=pattern_transfer(old,new,diff,inventory)
        self.assertEqual(result[0]["population_change"],"REMOVALS_ONLY")
        self.assertEqual(result[0]["removed_distinct_oracle_ids"],1)
        self.assertNotIn("precision",result[0])


if __name__=="__main__":
    unittest.main()
