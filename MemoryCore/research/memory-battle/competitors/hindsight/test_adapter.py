import unittest

from adapter import (
    AdapterContractError,
    describe_capabilities,
    normalize_graph_payload,
    normalize_memory_row,
    normalize_recall_payload,
    normalize_system_retrieved_records,
    resolve_source_document_ids,
    unsupported_localization_prediction,
)


class HindsightAdapterTest(unittest.TestCase):
    def test_native_id_preserved_without_fabricating_version(self):
        row = {
            "id": "f-1",
            "text": "Alice uses PostgreSQL",
            "fact_type": "world",
            "document_id": "l0-1",
            "chunk_id": "chunk-1",
        }
        node = normalize_memory_row(row)
        self.assertEqual(node.record_id, "f-1")
        self.assertEqual(node.document_id, "l0-1")
        self.assertIsNone(node.native_version)
        self.assertEqual(node.layer_proxy, "L1_PROXY")

    def test_observation_lineage_is_diagnostic_not_exact_edge(self):
        row = {
            "id": "obs-1",
            "text": "Alice prefers relational databases",
            "fact_type": "observation",
            "source_fact_ids": ["f-1", "f-2"],
        }
        node = normalize_memory_row(row)
        self.assertEqual(node.source_record_ids, ("f-1", "f-2"))
        self.assertEqual(node.layer_proxy, "L2_PROXY")
        edge = normalize_graph_payload(
            {"edges": [{"data": {"source": "f-1", "target": "obs-1", "linkType": "semantic"}}]}
        )[0]
        self.assertIsNone(edge["native_edge_version"])
        self.assertFalse(edge["exact_edge_eligible"])

    def test_recall_is_not_upgraded_to_exposure(self):
        normalized = normalize_recall_payload(
            {"results": [{"id": "f-1", "text": "x", "fact_type": "world", "scores": {"final": 1.0}}]}
        )
        self.assertEqual(normalized["trace"]["retrieved"][0]["record_id"], "f-1")
        self.assertEqual(normalized["trace"]["exposed"], [])
        self.assertEqual(normalized["trace"]["used"], [])

    def test_snapshot_hash_is_order_invariant(self):
        left = normalize_memory_row(
            {"id": "obs", "text": "x", "type": "observation", "source_memory_ids": ["a", "b"]}
        )
        right = normalize_memory_row(
            {"source_memory_ids": ["b", "a"], "type": "observation", "text": "x", "id": "obs"}
        )
        self.assertEqual(left.adapter_snapshot_hash, right.adapter_snapshot_hash)

    def test_missing_id_rejected(self):
        with self.assertRaises(AdapterContractError):
            normalize_memory_row({"text": "x", "fact_type": "world"})

    def test_capability_mismatch_is_strict_abstention(self):
        prediction = unsupported_localization_prediction("e-1")
        self.assertEqual(prediction["decision"], "abstain")
        self.assertIsNone(prediction["target_id"])
        self.assertIsNone(prediction["target_version"])
        self.assertFalse(prediction["optimization_ready"])
        self.assertFalse(describe_capabilities()["localization"]["exact_record_version"])

    def test_direct_fact_provenance_uses_only_native_document_id(self):
        resolution = resolve_source_document_ids(
            {
                "id": "f-1",
                "text": "x",
                "fact_type": "world",
                "document_id": "doc-1",
                "metadata": {"battle_document_id": "metadata-copy-must-not-win"},
            },
            None,
        )
        self.assertEqual(resolution.source_document_ids, ("doc-1",))
        self.assertTrue(resolution.complete)

    def test_missing_direct_provenance_is_empty_and_audited(self):
        resolution = resolve_source_document_ids(
            {
                "id": "f-1",
                "text": "x",
                "fact_type": "world",
                "metadata": {"battle_document_id": "known-but-not-native-document-id"},
            },
            None,
        )
        self.assertEqual(resolution.source_document_ids, ())
        self.assertFalse(resolution.complete)
        self.assertEqual(resolution.issues[0].reason, "native_document_id_missing")

    def test_observation_provenance_resolves_source_fact_map(self):
        resolution = resolve_source_document_ids(
            {
                "id": "obs-1",
                "text": "summary",
                "fact_type": "observation",
                "source_fact_ids": ["f-1", "f-2", "f-3"],
            },
            {
                "f-1": {"id": "f-1", "document_id": "doc-1"},
                "f-2": {"id": "f-2", "document_id": "doc-1"},
                "f-3": {"id": "f-3", "document_id": "doc-2"},
            },
        )
        self.assertEqual(resolution.source_document_ids, ("doc-1", "doc-2"))
        self.assertTrue(resolution.complete)

    def test_observation_missing_source_is_not_guessed(self):
        records, issues = normalize_system_retrieved_records(
            {
                "results": [
                    {
                        "id": "obs-1",
                        "text": "summary",
                        "fact_type": "observation",
                        "source_fact_ids": ["f-missing"],
                        "scores": {"final": 0.8},
                    }
                ],
                "source_facts": {},
                "source_facts_truncated": True,
            }
        )
        self.assertEqual(records[0]["nativeRecordId"], "obs-1")
        self.assertEqual(records[0]["sourceDocumentIds"], [])
        self.assertEqual(records[0]["score"], 0.8)
        self.assertEqual(issues[0]["reason"], "source_fact_not_returned")
        self.assertTrue(issues[0]["source_facts_truncated"])

    def test_system_mapping_caps_top_k_and_rehashes_native_text(self):
        rows = [
            {
                "id": f"f-{index}",
                "text": f"text-{index}",
                "fact_type": "experience",
                "document_id": f"doc-{index}",
                "scores": {"final": float(index)},
            }
            for index in range(7)
        ]
        records, issues = normalize_system_retrieved_records({"results": rows}, top_k=5)
        self.assertEqual(len(records), 5)
        self.assertEqual([record["rank"] for record in records], [1, 2, 3, 4, 5])
        self.assertEqual(records[-1]["sourceDocumentIds"], ["doc-4"])
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
