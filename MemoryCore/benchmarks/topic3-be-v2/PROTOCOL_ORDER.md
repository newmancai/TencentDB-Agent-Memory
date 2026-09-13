# Reader order development follow-up v2.1

Written after v2 qualification and before order outputs. The same 16 development
reuse tasks are intentionally reused to diagnose a failure, not to confirm a
held-out gain. Original v2 results remain unchanged.

Observation: native retrieval reaches all 21 labelled supporting user messages,
yet the reader sometimes chooses an earlier numeric value. Test whether a simple
ordering baseline explains the remaining gap before adding lifecycle semantics.

Compare oldest-first and newest-first on the exact same native top12 contents,
dates, question, Qwen model, greedy seed and 96-token output budget. Each input
has an explicit ordering field. A shared reader instruction says to use factual
timing and scope rather than assume the first or last item is correct. No E,
new evidence, answer labels, model learning or persistent memory mutation.
Both arms are run anew; their prompt differs from v2, so v2 is not substituted
as this experiment's baseline. Alternate execution order by task. Max32 calls.

Score with fixed official answers after execution; independently reviewed semantic
equivalence is separate from exact match. Improvement here is an input-order
development effect, not a B+E gain or a universal newest-wins rule. Historical,
condition-specific, cumulative and abstention queries remain in the cohort.
