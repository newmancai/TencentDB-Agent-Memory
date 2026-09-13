# v6.1 batch cost diagnosis, before new outputs

Written after v6 results. Same14 development pairs reused transparently, not an
independent confirmation. v6 spans locate3/5changed targets vs whole1/5, but35calls
vs14 and one extra unknown. Test batch label emission before adding a learned
selector. Native stored originals, full evidence, ordered targets and relation
semantics remain identical. One model call emits one A/B/C character per supplied
target, max16tokens for at most8targets. No JSON, target IDs or rewritten facts
generated. Host maps positions to exact fixed targets. Whitespace is ignored; any
other character or wrong label count invalidates this batch (errors reported).

Existing v6 independent-span and whole predictions are unchanged baselines whose
input/code/model were not modified. Only the new batch arm is run, no retries.
Report paired target decisions and pair-level quality plus actual costs. Gains
are development interface/cost effects, not policy learning or new gold evidence.
