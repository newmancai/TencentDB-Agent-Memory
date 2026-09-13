# v8.1: complete the same evidence reads

Written after v8 outputs, before new context-completion scores. Original v8 has
five context-limit receipts in two of17 RealMem cases (maximum30904tokens).
No input was truncated. Preserve original v8 outputs and metrics. Increase input
capacity to32768 only to complete those failed reads; keep all33 tasks, all three
prompts, model weights, labels, training feedback and score definitions fixed.
Reuse successful receipts exactly, so no selective regeneration of poor answers.

For these five previously unexecuted forwards, use Qwen3's local
`logits_to_keep=1` to avoid allocating full-sequence vocabulary logits. The model
still receives the entire input. This changes output allocation, not the evidence;
numerical results need not be bitwise equal to a hypothetical full-logit forward.
No quality improvement can be attributed to a new prompt or training strategy.
All arms receive the same raised cap and retain failures if32768 is insufficient.

Retain both protocols, metrics and resource costs. Reusing a receipt is not a new
model call. Fitting must yield the same policy because all16 fit cases had already
scored successfully. Treat this as post-output development repair of an input
capacity mismatch, not an independent confirmation or a new model comparison.
