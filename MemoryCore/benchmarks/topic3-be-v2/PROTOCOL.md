# Incoming-observation qualification v2

Written before new candidate/model outputs, 2026-09-12. Development reuse, not
held-out generalization: all 500 LongMemEval oracle questions were used previously.
This is a bounded diagnostic of the v1 failure, not a complete learning experiment.

Select the first eight knowledge-update and eight single-session-user questions
by SHA256(`topic3-be-v2:` + question_id), excluding the eight known full-s history
experiments of September 8 if their IDs are available before selection. Selection
does not use answers or a method's output. Use the complete cleaned s histories
from revision 98d7416c24c778c2fee6e6f3006e7a073259d48f. Non-KU is a sampling
stratum, not a no-change truth label. No new train/test split or policy fitting.

## Native incoming path

Allow-list role/content/date, replace all source/session/owner IDs with opaque
IDs, remove has_answer and every original answer-bearing identifier. Store full
messages in L0 and raw user chunks of at most 1600 characters through the native
L1 writer. Before each user chunk is written, retrieve eight prior chunks with
that incoming chunk as the query. No future source or final QA query enters this
path. Do not call a model on every chunk. Record the top-eight pool as a candidate
pool, not eight verified changes. A final native top-12 question retrieval is
retained as the ordinary answer baseline.

Offline source-label diagnostics report all source events, retrieval calls and
cost; supporting old-source reach at later supporting events; final native QA
source reach. Supporting turns/sessions are not exact obsolete-memory labels.
Neither of these reach metrics is task accuracy or high-confidence feedback.

## Known-target semantic qualification

For each selected question, offline select first/last answer-bearing user turns
from different sessions where available. Otherwise select the earliest preceding
user turn in the same session as the answer-bearing turn. This is explicitly
privileged target selection; no autonomy/discovery credit. Missing eligible pairs
remain missing, never replaced after model results.

Compare the frozen v1 E prompt against a role-aware prompt on the same full
turns and dates. The new prompt separates historical compatibility from changed
current use and recommends none/append/limit_current/unknown. Output <=128 tokens;
model Qwen3-4B-Instruct-2507, greedy, seed20260912, same existing local provider.
The question, official answer and support flags are not visible to either E.

For each of 16 official questions compare a fixed short-answer reader on (a)
native top12, (b) the same privileged full turns ordered by time, (c) those same
turns plus the role-aware E annotation. Reader max96 tokens, no continuation
repair. Model budget <=80 calls (32 E +48 readers); identical inputs may reuse
recorded deterministic outputs, charging logical costs per arm. Runtime inputs
have no answer. Official-answer scoring happens afterward. Strict normalized
exactness and separately explained semantic audit must not be conflated.

All E labels are fallible. Independent source review records whether a proposed
current-use transition is supported, with ambiguity retained. There is no global
semantic precision claim from sixteen items. No persistent update or learned
policy is warranted solely by this diagnostic.

If known-target annotation does not outperform the same evidence without labels,
do not claim E annotation value. If simple raw evidence fixes errors, locate the
retrieval bottleneck before adding lifecycle actions. If full incoming retrieval
still misses supporting old sources, investigate source-query representation;
do not compensate with larger E or use gold to select production candidates.
