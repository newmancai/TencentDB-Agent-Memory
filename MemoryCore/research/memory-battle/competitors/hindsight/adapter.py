"""Battle-safe normalization for Vectorize Hindsight 0.9.2.

This module deliberately does *not* turn Hindsight timestamps or content hashes
into native versions.  Hindsight is a memory system, not a Memory-fault judge;
its retrieval and graph output is useful in a system battle, while unsupported
localization rows must remain abstentions.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


PINNED_DISTRIBUTION = "hindsight-api-slim"
PINNED_VERSION = "0.9.2"
ADAPTER_VERSION = "hindsight-battle-adapter.v0.1"
PROTOCOL_VERSION = "memory-battle.v0.1-draft"


class AdapterContractError(ValueError):
    """Raised when native output lacks a field needed for lossless mapping."""


@dataclass(frozen=True)
class NativeMemoryNode:
    record_id: str
    fact_type: str
    layer_proxy: str
    text: str
    document_id: str | None
    chunk_id: str | None
    source_record_ids: tuple[str, ...]
    native_version: None
    adapter_snapshot_hash: str
    scores: Mapping[str, Any] | None
    mapping_qualification: str = "adapter_proxy_not_tdai_layer_gold"


@dataclass(frozen=True)
class RetrievedRecord:
    record_id: str
    rank: int
    scores: Mapping[str, Any] | None
    exposure_status: str = "retrieved_only"


@dataclass(frozen=True)
class DiagnosticEdge:
    from_record_id: str
    to_record_id: str
    relation: str
    native_edge_id: None
    native_edge_version: None
    adapter_fingerprint: str
    exact_edge_eligible: bool = False


@dataclass(frozen=True)
class ProvenanceIssue:
    record_id: str
    reason: str
    source_record_id: str | None = None
    source_facts_truncated: bool | None = None


@dataclass(frozen=True)
class ProvenanceResolution:
    source_document_ids: tuple[str, ...]
    complete: bool
    issues: tuple[ProvenanceIssue, ...]


def _require_string(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise AdapterContractError(f"native row requires non-empty string field {key!r}")
    return value


def _canonical_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_ids(row: Mapping[str, Any]) -> tuple[str, ...]:
    # Recall uses source_fact_ids; list/get-memory surfaces use source_memory_ids.
    raw = row.get("source_fact_ids")
    if raw is None:
        raw = row.get("source_memory_ids")
    if raw is None:
        return ()
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise AdapterContractError("source IDs must be an array when present")
    values: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item:
            raise AdapterContractError("source IDs must contain non-empty strings")
        values.append(item)
    return tuple(values)


def normalize_memory_row(row: Mapping[str, Any]) -> NativeMemoryNode:
    """Preserve native identity/provenance without inventing version semantics."""

    record_id = _require_string(row, "id")
    text = _require_string(row, "text")
    fact_type = row.get("fact_type", row.get("type"))
    if fact_type not in {"world", "experience", "observation"}:
        raise AdapterContractError(f"unsupported or missing fact type: {fact_type!r}")
    sources = _source_ids(row)
    scores = row.get("scores")
    if scores is not None and not isinstance(scores, Mapping):
        raise AdapterContractError("scores must be an object when present")

    digest_fields = {
        "id": record_id,
        "text": text,
        "fact_type": fact_type,
        "document_id": row.get("document_id"),
        "chunk_id": row.get("chunk_id"),
        "source_record_ids": sorted(sources),
        "state": row.get("state"),
        "edited_at": row.get("edited_at"),
        "updated_at": row.get("updated_at"),
    }
    return NativeMemoryNode(
        record_id=record_id,
        fact_type=fact_type,
        layer_proxy="L2_PROXY" if fact_type == "observation" else "L1_PROXY",
        text=text,
        document_id=row.get("document_id"),
        chunk_id=row.get("chunk_id"),
        source_record_ids=sources,
        native_version=None,
        adapter_snapshot_hash=_canonical_hash(digest_fields),
        scores=dict(scores) if scores is not None else None,
    )


def normalize_recall_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize recall while keeping retrieval distinct from exposure/use."""

    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise AdapterContractError("recall payload requires a results array")
    nodes = [normalize_memory_row(row) for row in raw_results]
    retrieved = [
        RetrievedRecord(record_id=node.record_id, rank=index + 1, scores=node.scores)
        for index, node in enumerate(nodes)
    ]
    return {
        "adapter_version": ADAPTER_VERSION,
        "nodes": [asdict(node) for node in nodes],
        "trace": {
            "retrieved": [asdict(item) for item in retrieved],
            # Hindsight recall does not observe what an external caller actually
            # injects into a downstream prompt or what the downstream model uses.
            "exposed": [],
            "used": [],
            "native_search_trace": payload.get("trace"),
        },
        "source_facts": payload.get("source_facts"),
        "source_facts_truncated": payload.get("source_facts_truncated"),
    }


def resolve_source_document_ids(
    row: Mapping[str, Any],
    source_facts: Mapping[str, Any] | None,
    *,
    source_facts_truncated: bool | None = None,
) -> ProvenanceResolution:
    """Resolve only provenance explicitly returned by Hindsight recall.

    World/experience units carry ``document_id`` directly.  Observations carry
    ``source_fact_ids`` and require the opt-in ``source_facts`` map to reach
    source documents.  Missing map entries are reported, never reconstructed
    from text, adapter metadata, ingestion order, or known battle documents.
    """

    record_id = _require_string(row, "id")
    fact_type = row.get("fact_type", row.get("type"))
    issues: list[ProvenanceIssue] = []
    document_ids: list[str] = []

    if fact_type in {"world", "experience"}:
        document_id = row.get("document_id")
        if isinstance(document_id, str) and document_id:
            document_ids.append(document_id)
        else:
            issues.append(ProvenanceIssue(record_id=record_id, reason="native_document_id_missing"))
    elif fact_type == "observation":
        source_ids = _source_ids(row)
        if not source_ids:
            issues.append(ProvenanceIssue(record_id=record_id, reason="observation_source_fact_ids_missing"))
        for source_id in source_ids:
            source = source_facts.get(source_id) if isinstance(source_facts, Mapping) else None
            if not isinstance(source, Mapping):
                issues.append(
                    ProvenanceIssue(
                        record_id=record_id,
                        reason="source_fact_not_returned",
                        source_record_id=source_id,
                        source_facts_truncated=source_facts_truncated,
                    )
                )
                continue
            native_source_id = source.get("id")
            if native_source_id != source_id:
                issues.append(
                    ProvenanceIssue(
                        record_id=record_id,
                        reason="source_fact_identity_mismatch",
                        source_record_id=source_id,
                        source_facts_truncated=source_facts_truncated,
                    )
                )
                continue
            document_id = source.get("document_id")
            if not isinstance(document_id, str) or not document_id:
                issues.append(
                    ProvenanceIssue(
                        record_id=record_id,
                        reason="source_fact_document_id_missing",
                        source_record_id=source_id,
                        source_facts_truncated=source_facts_truncated,
                    )
                )
                continue
            if document_id not in document_ids:
                document_ids.append(document_id)
    else:
        raise AdapterContractError(f"unsupported or missing fact type: {fact_type!r}")

    return ProvenanceResolution(
        source_document_ids=tuple(document_ids),
        complete=not issues,
        issues=tuple(issues),
    )


def normalize_system_retrieved_records(
    payload: Mapping[str, Any],
    *,
    top_k: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Map native recall into the common system-retrieval record contract.

    The second return value is an audit sidecar for provenance gaps.  A caller
    must persist those issues separately because the common prediction schema
    has no warnings field; the record's ``sourceDocumentIds`` remains empty or
    partial instead of being guessed.
    """

    if top_k <= 0:
        raise ValueError("top_k must be positive")
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise AdapterContractError("recall payload requires a results array")
    source_facts = payload.get("source_facts")
    if source_facts is not None and not isinstance(source_facts, Mapping):
        raise AdapterContractError("source_facts must be an object when present")
    truncated = payload.get("source_facts_truncated")
    if truncated is not None and not isinstance(truncated, bool):
        raise AdapterContractError("source_facts_truncated must be boolean when present")

    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for rank, row in enumerate(raw_results[:top_k], start=1):
        if not isinstance(row, Mapping):
            raise AdapterContractError("recall result must be an object")
        node = normalize_memory_row(row)
        provenance = resolve_source_document_ids(
            row,
            source_facts,
            source_facts_truncated=truncated,
        )
        final_score = node.scores.get("final") if node.scores is not None else None
        if isinstance(final_score, bool) or not isinstance(final_score, (int, float)):
            score = None
        else:
            numeric_score = float(final_score)
            score = numeric_score if math.isfinite(numeric_score) else None
        records.append(
            {
                "nativeRecordId": node.record_id,
                "rank": rank,
                "score": score,
                "sourceDocumentIds": list(provenance.source_document_ids),
                "content": node.text,
                "contentSha256": hashlib.sha256(node.text.encode("utf-8")).hexdigest(),
            }
        )
        issues.extend(asdict(issue) for issue in provenance.issues)
    return records, issues


def normalize_graph_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return diagnostic links; none qualify as exact versioned battle edges."""

    raw_edges = payload.get("edges")
    if not isinstance(raw_edges, list):
        raise AdapterContractError("graph payload requires an edges array")
    normalized: list[dict[str, Any]] = []
    for wrapper in raw_edges:
        if not isinstance(wrapper, Mapping):
            raise AdapterContractError("graph edge must be an object")
        data = wrapper.get("data", wrapper)
        if not isinstance(data, Mapping):
            raise AdapterContractError("graph edge data must be an object")
        source = _require_string(data, "source")
        target = _require_string(data, "target")
        relation = _require_string(data, "linkType")
        fingerprint = _canonical_hash(
            {
                "from": source,
                "to": target,
                "relation": relation,
                "entity": data.get("entityName"),
            }
        )
        normalized.append(
            asdict(
                DiagnosticEdge(
                    from_record_id=source,
                    to_record_id=target,
                    relation=relation,
                    native_edge_id=None,
                    native_edge_version=None,
                    adapter_fingerprint=fingerprint,
                )
            )
        )
    return normalized


def unsupported_localization_prediction(example_id: str) -> dict[str, Any]:
    """Represent capability mismatch as an honest abstention, not a fake miss."""

    return {
        "schema_version": "prediction.v0.1",
        "protocol_version": PROTOCOL_VERSION,
        "example_id": example_id,
        "decision": "abstain",
        "target_type": None,
        "target_id": None,
        "target_version": None,
        "edge_endpoints": None,
        "supporting_ids": [],
        "fault_type": None,
        "suggested_action": None,
        "confidence": 0.0,
        "abstain_reason_codes": [
            "competitor_has_no_native_feedback_localizer",
            "native_record_version_unavailable",
        ],
        "evidence": [],
        "replay_status": "not_run",
        "optimization_ready": False,
    }


def describe_capabilities() -> dict[str, Any]:
    """Pinned capability declaration used by harness admission checks."""

    return {
        "adapter_version": ADAPTER_VERSION,
        "distribution": PINNED_DISTRIBUTION,
        "version": PINNED_VERSION,
        "comparison_modes": ["system"],
        "eligible_tracks": ["GEN", "retrieval-diagnostic"],
        "localization": {
            "native_fault_prediction": False,
            "exact_record_version": False,
            "exact_edge_version": False,
            "policy": "abstain_on_LOC_rows_unless_a_separate_common_judge_is_declared",
        },
        "identity": {
            "memory_unit_uuid": True,
            "document_id": True,
            "chunk_id": True,
            "source_fact_ids": True,
            "immutable_source_fact_version": False,
            "adapter_snapshot_hash_is_native_version": False,
        },
        "graph": {
            "memory_links": True,
            "native_edge_version": False,
            "visualization_edge_id_is_versioned": False,
            "observation_to_source_ids": True,
        },
        "history": {
            "source_fact_edit_history": False,
            "source_fact_edited_at": True,
            "source_fact_invalidation_archive": True,
            "observation_history": True,
            "mental_model_history": True,
        },
        "trace": {
            "recall_stage_trace": True,
            "per_result_stage_scores": True,
            "external_prompt_exposure": False,
            "external_model_use": False,
            "reflect_based_on_and_tool_trace": True,
        },
        "export": {
            "document_transfer": True,
            "document_transfer_preserves_database_ids": False,
            "knowledge_base_markdown": True,
            "full_id_preserving_graph_snapshot": False,
        },
    }
