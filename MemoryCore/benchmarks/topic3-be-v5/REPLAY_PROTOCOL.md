# v5.1 partial-feedback replay: written after v5 outputs, before replay scoring

v5's all-or-nothing decision contract rejects every target if an unrelated target
omits new IDs or a decision. This is unnecessarily strict for independent
candidate feedback. An unknown does not assert a change and needs no supporting
later quote. Preserve original v5 outputs and scores.

Replay the SAME recorded responses, with no new model calls and no prompt edits.
Extraction remains unchanged (including whole-extraction failures). For each
existing immutable target: accept a unique legal decision; unknown permits empty
or absent new_ids; changed/same still require legal later IDs. Missing, malformed,
duplicate or unsupported decisions become unknown ONLY for that target. Reject
unknown target IDs and extra fields that might mutate a target. Never fabricate
new evidence or convert a missing decision to same. Record each issue.

Report v5 strict and v5.1 replay separately. This tests host failure isolation,
not semantic improvement or generalization. Any apparent gain is post-output
development replay, not a newly held-out result. Model costs are inherited in
full; original errors remain charged. Correctness must still require target
identity and factual support, not merely aggregate relation agreement.
