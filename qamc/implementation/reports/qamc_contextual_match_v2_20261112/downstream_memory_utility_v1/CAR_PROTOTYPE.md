# Counterfactual Action Realization prototype

Status: the deterministic output operation, controller contracts, and Actor exposure adapters are implemented and structurally tested. Endpoint answer availability, preregistration, job dispatch, generation, and scoring remain to be completed. No experimental results from this prototype enter the manuscript.

## Shared inputs and comparison

The same task, public facts, frozen source inventory and Actor feed an empty-history and a complete-history answer. Archived endpoints qualify for reuse only when their inputs and service are compatible with the frozen comparison. The same controller proposes at most one concrete action and identifies the historical source and the actor and beneficiary of that action. When justified, the Actor produces one new complete answer using the verified source subset in its existing input channel. A source-use instruction may be added only if the frozen Actor interface already has such a channel. Neither the proposal nor author labels can be passed as user facts.

The three treatments receive the same complete candidates, proposal, sources, and protection information. They share the exact protected-literal check and fixed fallback. [Controller prompts and parser](controller.py) With one equal-budget control call each, one selects a complete answer, one freely revises or keeps an existing answer, and one selects or performs the copy-only transaction below. Count all upstream cold-start calls, including shared calls and cached counterparts. Keep omitted or failing candidates visible in the per-arm ledger. Use original IPE-C, Strong Gate, and PB_RUBRIC or SELECTED_GEPA as separate method-level references under documented project scoring adaptations.

## Executable operation

Reuse the original lossless paragraph segmenter from the TATR assembler. Freeze the returned block IDs for every complete candidate in the controller prompt. It can return `SELECT` and a complete candidate ID, or `COMMIT` with a base, a distinct donor, and paired block ranges. Ranges are zero-indexed and half-open. Multiple replacements may be disjoint but are validated together. Every nonempty donor range is copied verbatim, remains in source order, and is used at most once. An empty base range means insertion. A rejected transaction returns a predesignated full candidate exactly and records a contract fallback. Transport and missing-answer failures do not silently become semantic scores.

The output may include the selected location and a corresponding invitation from the same new answer while retaining other base blocks. The program guarantees literal byte preservation, ordered nonoverlapping ranges and declared literal checks. Whether all semantically dependent blocks were included still requires controller judgment and actual behavior evaluation. An action affecting the whole document is comparable to full-answer selection and counts separately. A transaction that equals any existing full answer must be recorded as a selection.

This differs from the former TATR assembler, which starts from one archived answer and accepts new text under WRITE or INSERT. It also differs from CDC's program veto over existing complete answers and DREW's model-generated replacement text. CAR requires a newly generated donor that actually exhibits a proposed behavior before the constrained commit. The method comparison must establish whether either donor availability or the copy-only operation improves results. A new name and additional calls alone add no empirical support. [PURPLE transfer audit](PURPLE_ADOPTION.md) · [TATR results](../transactional_reassembly_v1/REPORT.md)

## Genuine task checks for the freeze

- RPEval: in the parent anniversary task, the requester can make a complete gift without assigning craft participation to their parents. Compare both author's released variants only after independent inference. Test similarly for a Spanish practice activity carried out by the requester. Keep an explicit C protection case. No paired-answer identity or author label enters inference.
- BenchPreS: a legitimate brevity or objective-voice attribute must visibly change the delivered message without changing facts, request, and necessary caveats. A concise message is not necessarily complete and a preserved literal may still appear in a false relationship. Include examples where the original draft already complies.
- PersistBench: a cat-free main book-club plan must be consistent with the invitation, not offered merely as an optional alternative. Measure CD and SYC separately and protect strict BU. Keep cases in which the full public task is already satisfied without using private history.

While freezing, establish both the score-level thresholds and the opportunity-level facts that differentiate the mechanisms. Report candidate coverage and actual action execution before committed and scored counts. Two treatment variants with identical final bytes are not two semantic outcomes. Where the controller cannot obtain a distinct behavior or the commit does not beat strong ordinary selection and revision without sacrifices, preserve the failure and do not promote the mechanism.

## Offline structural check

```sh
python3 -m unittest discover -s . -p test_action_commit.py
```

## Actor exposure wire acceptance

A read-only replay used 296 archived RP requests from RPEval, 43 Strong Gate requests from BenchPreS, and 60 PB_RUBRIC requests from PersistBench. All reconstructed the exact previously exposed request and produced an empty-history request with the same task, settings and static prompt. BenchPreS Strong Gate's archived exposure is its selected subset. The adapter verifies those sources against the full frozen task list and can use the original list to make a new exposure. The replay checked wire structure only. It establishes no answer reusability or model behavior.

- RPEval can reuse the existing per-source A/B/C policy channel. It has no free-text action field.
- BenchPreS can reuse original source text plus the existing bounded per-source guidance, with the visible position recomputed after exposure.
- PersistBench's pinned PB_RUBRIC renderer has a history slot inside the system template and an unchanged query. It has no free-text usage channel. In the strict frozen arm, the controller's proposal can condition the history exposure and downstream comparison but cannot directly instruct that Actor. Prompts rendered with different histories will differ only through the native history slot. Claims of the same direct generation guidance on all three would require a separate interface intervention.

The private replay requires the original execution workspace and pinned author checkout. It emits only aggregate counts and performs zero requests. The archive contains the adapter and audit entry point. [Exposure adapter](exposure_wires.py) · [Replay](audit_exposure_wires.py)
