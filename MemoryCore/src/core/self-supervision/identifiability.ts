import { canonicalHash } from "./observation-plane.js";
import type {
  CompleteFeedbackTuple,
  CompleteTupleIdentifiabilityCertificate,
  IdentifiabilityBasis,
  IdentifiabilityStatus,
  LayerSignalEvidence,
} from "./types.js";

type CompleteTupleLike = Pick<CompleteFeedbackTuple, "target" | "faultType" | "suggestedAction">;

const AUTHORITY_EVIDENCE_KINDS: Record<IdentifiabilityBasis, Set<LayerSignalEvidence["kind"]>> = {
  capture_authority: new Set(["l0_l1_provenance", "l1_l2_derivation"]),
  deterministic_graph: new Set(["l1_l1_consistency", "l1_l2_derivation", "l2_l2_consistency"]),
  objective_oracle: new Set(["task_intervention", "negative_control"]),
};

function sortedUnique(values: string[]): string[] {
  return [...new Set(values)].sort();
}

function sameStrings(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function assertOnlyKeys(value: object, allowed: readonly string[], field: string): void {
  const allowedSet = new Set(allowed);
  const unknown = Object.keys(value).find((key) => !allowedSet.has(key));
  if (unknown) throw new Error(`${field} contains unsupported field ${unknown}`);
}

function assertPositiveVersion(value: number, field: string): void {
  if (!Number.isSafeInteger(value) || value < 1) throw new Error(`${field} must be a positive integer`);
}

function assertExactTupleVersions(tuple: CompleteTupleLike): void {
  assertPositiveVersion(tuple.target.targetVersion, "identifiability target version");
  if (tuple.target.targetType === "L1_L2_EDGE") {
    assertPositiveVersion(tuple.target.from.version, "identifiability edge from.version");
    assertPositiveVersion(tuple.target.to.version, "identifiability edge to.version");
  }
}

function exactTarget(target: CompleteTupleLike["target"]): CompleteTupleLike["target"] {
  if (target.targetType === "L1_NODE" || target.targetType === "L2_NODE") {
    return {
      targetType: target.targetType,
      targetId: target.targetId,
      targetVersion: target.targetVersion,
    };
  }
  return {
    targetType: "L1_L2_EDGE",
    targetId: target.targetId,
    targetVersion: target.targetVersion,
    from: { layer: "L1", id: target.from.id, version: target.from.version },
    to: { layer: "L2", id: target.to.id, version: target.to.version },
  };
}

/** Includes edge endpoints, so an edge ID with mismatched versions cannot alias. */
export function completeFeedbackTupleKey(tuple: CompleteTupleLike): string {
  return `tuple-${canonicalHash({
    target: exactTarget(tuple.target),
    faultType: tuple.faultType,
    suggestedAction: tuple.suggestedAction,
  })}`;
}

export function completeFeedbackCandidateSetHash(tupleKeys: string[]): string {
  return canonicalHash(sortedUnique(tupleKeys));
}

export function createCompleteTupleIdentifiabilityCertificate(input: {
  verifierId: string;
  basis: IdentifiabilityBasis;
  status: IdentifiabilityStatus;
  candidateTuples: CompleteTupleLike[];
  identifiedTuple?: CompleteTupleLike;
  competingTuples?: CompleteTupleLike[];
  noSignalWorldExcluded: boolean;
  evidence: LayerSignalEvidence[];
  reasonCodes: string[];
}): CompleteTupleIdentifiabilityCertificate {
  input.candidateTuples.forEach(assertExactTupleVersions);
  if (input.identifiedTuple) assertExactTupleVersions(input.identifiedTuple);
  (input.competingTuples ?? []).forEach(assertExactTupleVersions);
  const candidateTupleKeys = sortedUnique(input.candidateTuples.map(completeFeedbackTupleKey));
  return {
    schemaVersion: "tdai-complete-tuple-identifiability.v1",
    verifierId: input.verifierId,
    basis: input.basis,
    status: input.status,
    candidateSetHash: completeFeedbackCandidateSetHash(candidateTupleKeys),
    candidateTupleKeys,
    identifiedTupleKey: input.identifiedTuple ? completeFeedbackTupleKey(input.identifiedTuple) : null,
    competingTupleKeys: sortedUnique((input.competingTuples ?? []).map(completeFeedbackTupleKey)),
    noSignalWorldExcluded: input.noSignalWorldExcluded,
    evidence: structuredClone(input.evidence),
    reasonCodes: [...input.reasonCodes],
  };
}

/**
 * Validates both certificate semantics and its binding to the exact structural
 * candidate universe. It deliberately accepts no score or confidence field.
 */
export function assertCompleteTupleIdentifiabilityCertificate(
  certificate: CompleteTupleIdentifiabilityCertificate,
  candidates?: CompleteTupleLike[],
  expectedVerifierId?: string,
): void {
  const raw = certificate as unknown as Record<string, unknown>;
  if ("score" in raw || "rawScore" in raw || "confidence" in raw) {
    throw new Error("Identifiability cannot be certified by a score or confidence");
  }
  assertOnlyKeys(certificate, [
    "schemaVersion",
    "verifierId",
    "basis",
    "status",
    "candidateSetHash",
    "candidateTupleKeys",
    "identifiedTupleKey",
    "competingTupleKeys",
    "noSignalWorldExcluded",
    "evidence",
    "reasonCodes",
  ], "Identifiability certificate");
  if (certificate.schemaVersion !== "tdai-complete-tuple-identifiability.v1") {
    throw new Error("Unknown complete-tuple identifiability certificate schema");
  }
  if (!certificate.verifierId.trim()) throw new Error("Identifiability verifierId is required");
  if (expectedVerifierId !== undefined && certificate.verifierId !== expectedVerifierId) {
    throw new Error("Identifiability certificate verifier does not match invoked verifier");
  }
  if (!(new Set<IdentifiabilityBasis>(["capture_authority", "deterministic_graph", "objective_oracle"]))
    .has(certificate.basis)) {
    throw new Error("Identifiability certificate must use a non-model authority basis");
  }
  if (!(new Set<IdentifiabilityStatus>(["identified", "ambiguous", "insufficient_evidence"]))
    .has(certificate.status)) {
    throw new Error("Unknown identifiability status");
  }
  const canonicalCandidateKeys = sortedUnique(certificate.candidateTupleKeys);
  if (!sameStrings(certificate.candidateTupleKeys, canonicalCandidateKeys)) {
    throw new Error("Identifiability candidate tuple keys must be sorted and unique");
  }
  if (certificate.candidateSetHash !== completeFeedbackCandidateSetHash(canonicalCandidateKeys)) {
    throw new Error("Identifiability certificate candidate-set hash mismatch");
  }
  if (candidates) {
    candidates.forEach(assertExactTupleVersions);
    const actualKeys = sortedUnique(candidates.map(completeFeedbackTupleKey));
    if (!sameStrings(actualKeys, canonicalCandidateKeys)) {
      throw new Error("Identifiability certificate is not bound to the structural candidate set");
    }
  }
  const competitorKeys = sortedUnique(certificate.competingTupleKeys);
  if (!sameStrings(certificate.competingTupleKeys, competitorKeys)) {
    throw new Error("Identifiability competing tuple keys must be sorted and unique");
  }
  if (competitorKeys.some((key) => !canonicalCandidateKeys.includes(key))) {
    throw new Error("Identifiability certificate names a competitor outside the candidate set");
  }

  if (certificate.status === "identified") {
    if (!certificate.identifiedTupleKey || !canonicalCandidateKeys.includes(certificate.identifiedTupleKey)) {
      throw new Error("Identified tuple is not in the structural candidate set");
    }
    if (!certificate.noSignalWorldExcluded) {
      throw new Error("Identifiability requires the no-signal world to be excluded");
    }
    if (competitorKeys.length > 0) throw new Error("Identifiability has unresolved competing tuples");
    if (certificate.evidence.length === 0) throw new Error("Identifiability requires authority evidence");
    const allowedKinds = AUTHORITY_EVIDENCE_KINDS[certificate.basis];
    for (const evidence of certificate.evidence) {
      assertOnlyKeys(evidence, ["kind", "supportingIds", "claim", "evidenceHash", "verifierId"], "Authority evidence");
      if (!allowedKinds.has(evidence.kind)) {
        throw new Error(`Evidence kind ${evidence.kind} cannot certify ${certificate.basis} identifiability`);
      }
      if (evidence.verifierId !== certificate.verifierId) {
        throw new Error("Authority evidence verifier does not match the identifiability verifier");
      }
      if (!evidence.claim.trim() || !/^[a-f0-9]{64}$/i.test(evidence.evidenceHash)) {
        throw new Error("Identifiability authority evidence is malformed");
      }
      if (evidence.supportingIds.length === 0 || evidence.supportingIds.some((id) => !id.trim())) {
        throw new Error("Identifiability authority evidence requires supporting IDs");
      }
    }
    if (certificate.reasonCodes.length === 0) throw new Error("Identifiability requires a reason code");
    return;
  }

  if (certificate.identifiedTupleKey !== null) {
    throw new Error("Non-identified certificate cannot name an identified tuple");
  }
  if (certificate.status === "ambiguous" && competitorKeys.length === 0 && certificate.noSignalWorldExcluded) {
    throw new Error("Ambiguous certificate must retain a competing tuple or no-signal world");
  }
}

export function assertCertificateIdentifiesTuple(
  certificate: CompleteTupleIdentifiabilityCertificate,
  tuple: CompleteTupleLike,
): void {
  assertExactTupleVersions(tuple);
  assertCompleteTupleIdentifiabilityCertificate(certificate);
  if (certificate.status !== "identified") throw new Error("Emitted signal requires an identified tuple certificate");
  if (certificate.identifiedTupleKey !== completeFeedbackTupleKey(tuple)) {
    throw new Error("Identifiability certificate does not match the emitted complete tuple");
  }
}
