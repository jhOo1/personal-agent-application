# Joint control of the plan and original history

Status at freeze: initial 40-task exposed development comparison. The three original benchmarks remain. The source-disjoint 162-task expansion has already informed the design and is also development data. Sealed data is outside the run.

The current Scope Actor points to an intermediate, task-only model plan as guidance. In the preceding control, holding that plan fixed and changing only history did not reach the archive specialist on RPEval, even when choosing the best saved exposure endpoint per task after scoring. The plan may independently anchor a poor default or suppress a useful preference. Emptying the plan also tests an interface limitation, since the Actor instruction about plans remains constant.

All arms read the same frozen task and fixed original memory. Their online controllers receive the same input, model and token cap. The first ordinary Gate seed learns no offline policy feedback, just like the first joint seed. Subsequent fit iterations would need the same feedback and optimization budget.

- OPT_GATE uses the shared eligibility prompt and chooses no history, the existing subset, or full history. It retains the existing plan.
- JCC_KEEP uses the joint controller's actual raw subset and retains the plan.
- JCC executes the same controller receipt and may empty the plan. JCC and JCC_KEEP share the actual request whenever the joint controller retains the plan.

Only ordered original sources and either the original plan or an empty plan reach the same Scope Actor. The online controller does not receive benchmark names, evaluation scores, labels, old answers, or route decisions. Task, facts, group, raw candidates, sampler and output cap stay fixed. The published controller code contains the complete prompts. Scorer roles remain segregated. Invalid or unknown deliveries remain missing.

Primary comparison: project-compatible RPEval Match, BenchPreS AAR/MR/completeness, and PersistBench risk plus strict beneficial use, on matched cases. Specialist reference is IPE-C, Strong Gate, or PB_RUBRIC according to benchmark. Inspect RPEval OPB/UPB/FM and protect explicit constraints, preserve BenchPreS delivery, and protect strict beneficial use. A plan-removal causal claim needs a same-source contrast with actual behavioral changes on multiple source roots. The gate contrast changes both decision instructions and selection action space. Positive fit results are eligibility for an exposed expansion, with no SOTA or held-out claim. Main-paper comparison requires verified equivalent evaluation against external strong methods.

Reuse the existing engine for committed request receipts, exact cache, dispatch limits, and frozen scoring adapters. An identical Scope answer uses its existing score. No retry of delivery-unknown calls. No original output is replaced. Restore the private fit archive and provider configuration before freeze/check/run; report is zero dispatch. Entry: run.sh joint-context freeze|check|run|report.
