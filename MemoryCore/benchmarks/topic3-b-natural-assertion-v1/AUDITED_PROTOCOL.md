# Pre-audited raw correction diagnostic

2026-09-13. This addendum was written after v1 exposed a label-contract mismatch
and before selecting or running v2. The model prompt, model, reasoning effort,
schema, exact-span requirement, and no-retry rule remain unchanged.

V1 used the public `NEG_2` behaviour label as an assertion-proposal gold label. A
post-output source review found that three of four selected `NEG_2` messages were a
new edit/continuation/format request without both an identified error and explicit
replacement content. Therefore the v1 `9/12` threshold failure is retained, but it
cannot be interpreted as three model false negatives under the stricter assertion
contract.

V2 selects, by a new fixed hash and distinct conversations, eight previously unselected
WildChat `NEG_2` cases plus two `NEG_3` and four `NEG_4` cases. The main agent reads
the raw three-message packet and freezes `propose`/`abstain` labels under the v1
contract **before any v2 model call**. All twenty selected cases remain in the run;
cases are not removed for ambiguity or class balance. Public behaviour labels remain
metadata only.

The fixed v2 exit rule is:

- 14/14 calls complete;
- at least two pre-audited `propose` cases exist, otherwise the sample has
  insufficient positive coverage and cannot pass;
- at least 12/14 exact action+schema+span checks pass;
- at most one miss in the `propose` group and at most one miss in the `abstain`
  group.

The pre-audit is a declared main-agent source judgment, not independent annotation.
This is still a development capability check over previously reused public data, not
a prevalence estimate or final generalization result. Passing permits host-integrated
candidate construction; it does not permit durable promotion or memory-cause claims.

Feasibility amendment, still before selection or model calls: the initial draft asked
for twelve new `NEG_2` conversations, but the fixed WildChat source has only thirteen
such conversations total and v1 already consumed four. The selector failed closed
without writing a task packet. The count was reduced to the maximum practical balanced
diagnostic above. Requiring uniqueness across all labels leaves only two new `NEG_3`
conversations after taking the eight `NEG_2` cases, so the second failed-closed
selection attempt reduced that cell from four to two. No task packet, message content,
or model result was inspected before either feasibility change.
