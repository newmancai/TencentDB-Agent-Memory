# Web-disabled, filesystem-isolated held-out v4 results

Date: 2026-09-14. This is the first admissible route-v2 held-out matrix. The three earlier attempts
remain invalid and contribute no row.

## Outcome

All 24 Codex calls completed. Every receipt says `filesystem_isolated=true`; all 24 raw event logs
contain no `web_search` event, benchmark checkout path, output path, or sibling workspace path. There
were no agent execution failures, missing usage records, memory errors, or compatibility regressions.
The copied manifest and live manifest retain the frozen SHA-256
`7038fc0ee481c7ffcb22261d0eebd5ac31cd0c08c72f7c2b162a0d48c08d34c9`; the checker retains
`205122a5525089f22d63cd068622f886b98251a99f882020d1c8906387e466c3`. The final receipts and
summary hashes are `3727d417ec53e53f078f660def6b30f50b5f19bf1043a3cf6e841c2dc10a406c` and
`38df71b1973108f3576f3059b2106bc24b99a67caebf28957bc87179d709fdad` respectively.

| Task | Kind | No history | Full raw | Raw top-8 |
| --- | --- | ---: | ---: | ---: |
| packaging unbounded canonicalization | necessary update | pass / 129.899 s | pass / 122.833 s | pass / 150.482 s |
| packaging bounded control | same-topic control | pass / 98.303 s | pass / 52.126 s | pass / 55.516 s |
| Flask IPv6 authority | necessary update | pass / 168.257 s | pass / 160.553 s | pass / 123.291 s |
| Flask hostname control | same-topic control | pass / 95.763 s | pass / 94.734 s | pass / 91.555 s |
| tqdm unknown length | necessary update | **fail / 136.968 s** | pass / 89.014 s | pass / 100.772 s |
| tqdm known-length control | cumulative control | **fail / 89.134 s** | pass / 46.234 s | pass / 70.714 s |
| Uvicorn pipelined upgrade | necessary update | pass / 155.167 s | pass / 179.297 s | pass / 187.785 s |
| Uvicorn pipelined HTTP control | same-topic control | pass / 82.723 s | pass / 92.284 s | pass / 90.760 s |

Full raw and top-8 each passed 8/8; no-history passed 6/8. The aggregate summary mechanically reports
two paired wins because the second task runs on each arm's accumulated code. This is one independent
project-family success, not two independent memory wins: no-history failed the initial tqdm update,
and the following control continued to fail because that incorrect implementation remained.

## Observed useful mechanism

The tqdm request said not to consume generators and to preserve known-length behavior. Without
history, the agent implemented a plausible policy: return `None` when *any* iterable has an unknown
length and update a downstream comparison. That fails the accepted behavior when an unknown-length
generator is paired with a sized iterable. Both raw arms retrieved the earlier decision that unknown
hints are ignored, the minimum known hint is retained, and zero is used only when no known hint
exists. They implemented that policy and passed the cumulative control.

This is direct behavioral evidence that lossless project history can resolve an otherwise ambiguous
maintenance decision. It is limited to one of four independent project families, prepared from real
review decisions but replayed as authored sequential user observations. It does not establish a
population success rate, natural-user benefit, or superiority to an external memory product.

## Cost and route decision

| Arm | Pass | Total input | Cached input | Uncached input | Output | Reasoning output | Wall sum | Context bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no history | 6/8 | 2,919,958 | 2,676,224 | 243,734 | 31,169 | 10,218 | 956.214 s | 0 |
| full raw | 8/8 | 2,039,342 | 1,837,184 | 202,158 | 27,409 | 8,178 | 837.074 s | 16,484 |
| raw top-8 | 8/8 | 2,190,824 | 1,941,888 | 248,936 | 29,413 | 9,195 | 870.874 s | 11,398 |

Against no-history, full raw gained the tqdm project result while using 30.16% less total input,
17.06% less uncached input, 12.06% less output, and 12.46% less wall time in this run. Execution order
was rotated but each cell was sampled once, so these savings are promising paired-run evidence rather
than stable latency estimates.

Top-8 tied full raw on quality and reduced rendered context bytes by 30.86%, but used 7.43% more total
input, 23.14% more uncached input, 7.31% more output, and 4.04% more wall time. Under the frozen rule,
the top-8 efficiency candidate is **closed**, not promoted or tuned on v4. Smaller injected context
did not reduce end-to-end agent work.

The product decision is to retain lossless full raw as the current default and treat its useful effect
as a replication candidate. Do not add compilation, learned selection, or a new retrieval layer from
this matrix. Before stronger adoption language, repeat the result on new project/scenario families or
another backend under the same two isolation layers, and count project families rather than
cumulative task rows.

Raw evidence is at `.local-evidence/project-agent-route-v2-heldout-v4/results-v1`: manifest, 24
receipts, summary, exact contexts, prompts, agent event logs, checkers, usage, and workspace diffs.
