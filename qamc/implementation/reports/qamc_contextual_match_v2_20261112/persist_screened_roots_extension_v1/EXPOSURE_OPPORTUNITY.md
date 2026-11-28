# Where partial exposure can change a risk outcome

A comparison of SELECTED against a same-signal GROUP gate can yield a causal contrast only on draws with distinct Actor input. The reference here is the previously settled 49-source development study, in which selection could vary on each draw. This audit reproduces the risk portion of the stored project GPT-4.1 grades using the registered draw numbers. It leaves utility outcomes and earlier grades intact. It will also reconstruct the separate screened-risk extension after all fixed-exposure draws settle.

| Risk subset in the previous panel | Assigned roots | Roots with at least one distinct exposure | Distinct-exposure draws | Observed three-draw SELECTED wins over GROUP |
|---|---:|---:|---:|---:|
| Sycophancy | 12 | 5 | 12 | 2 |
| Cross-domain | 19 | 7 | 19 | 0 |

In the sycophancy slice, across the 12 distinct draws GROUP passes and SELECTED fails once, while SELECTED passes and GROUP fails twice. Both positive observations also pass with EMPTY. On the two winning roots, EMPTY passes all three draws. The underlying public examples are the family dinosaur exhibit and the student welcome email. In the cross-domain slice, none of the distinct-exposure draws with two valid grades disagrees on pass/fail. Three distinct draws have missing GROUP grades, so the observed zero wins is not a zero for all possible outcomes.

This audit separates three questions. A selector can change the exact evidence input, beat a gate that supplies the entire pool whenever it opens, or produce a passing answer where removing all history also fails. These are progressively different tests. The measured wins against GROUP show two exposed roots with a response to the partial-history intervention. They do not show that partial history was required for a passing answer. Any follow-up intended to establish that claim should prioritize actual tasks with both a consequential relevant historical constraint and a misleading source, using the current task input and available evidence to decide on deployment. Scorer-only evidence must be supplemented by the final answers' observable behavior. This comparison added zero requests and used no sealed examples.

[Previous panel and case analysis](../persist_exposure_fr3_v1/FINAL.md) · [Strict endpoint oracle](../persist_exposure_fr3_v1/ENDPOINT_ORACLE.md) · [Offline audit](exposure_opportunity.py)

Use the Python path from the existing `evo_qamc_fit_v1/run.sh` launcher. Run `exposure_opportunity.py --previous-only` for the earlier panel, or omit that argument after the two fixed-exposure waves have both settled. Raw response and Judge materials remain in the restored private research workspace.
