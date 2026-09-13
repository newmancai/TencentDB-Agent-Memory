# Behavior-checker authoring standard after v9

Date: 2026-09-14. This is a prospective evaluation requirement. It does not repair v9 or rescore an
earlier matrix.

For every semantic clause named in a held-out task, the preparation record must contain a concrete
behavioral witness. A checker is frozen only after all of these classes are exercised:

1. the declared base passes compatibility and fails the target behavior;
2. the reviewed implementation passes compatibility and every target/control witness;
3. an independently written equivalent implementation also passes;
4. at least one independently written **near-miss** per critical boundary fails while still satisfying
   the obvious headline behavior.

Near-misses are not arbitrary broken code. They model plausible partial fixes: only one field width,
right exception with a broken directory control, FIFO without the concurrency boundary, value equality
before exact-type equality, wrong warning frame, or a rule applied outside its scope. The protocol must
map every statement such as “before”, “only”, “unless”, “preserve”, or “does not refresh” to a positive
or negative witness before the first model call.

Preparation stores the exact patches and hashes for base, reviewed, equivalent, and near-miss variants.
All variants run both the necessary-update and cumulative-control stages. A post-run patch audit remains
mandatory; if an accepted cell violates a declared clause, the whole matrix is invalid even when the
frozen checker passed. Post-hoc probes are diagnostic only and cannot add wins.

This standard complements filesystem, web-search, revision, receipt, and output-path isolation. It does
not justify adding implementation-string checks or privileged future code to an agent workspace.
