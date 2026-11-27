# BenchPreS fixed-response preference reflection validation

The follow-up evaluates whether saved final answers exhibit the supplied preference. It keeps the author appropriateness labels and original Qwen grades for analysis after review. BenchPreS Appendix E separates reflection detection from contextual appropriateness. Its authors compare human and model judgments on 300 balanced instances. This follow-up uses all available answers from the project's exposed repeat panel, with two method-masked review orders and an uncertainty option. [BenchPreS Appendix E and Figure 12](https://aclanthology.org/2026.emnlp-main.1040.pdf#page=12) · [Original repeat result](FINAL_READOUT.md)

## Frozen inventory

| Quantity | Count |
| --- | ---: |
| Allocated method–task–draw cells | 288 |
| Available Strong Gate answers | 119 |
| Available Selectivity answers | 130 |
| Paired available answers | 115 |
| Paired answers with complete original Qwen scores | 106 |
| Available answers without an opposite-arm answer | 19 |
| Cells without a usable answer | 39 |
| Attribute judgments allocated per reviewer | 1,245 |
| Reviewers with submitted judgments | 0 |

The inventory reproduces the archived original allocation and scores, verifies each available Actor request, and reconstructs all six grading wires per saved answer. Raw answers, review packets, the seed and the identity mapping remain private. The two orders use separate opaque IDs and expose only the attribute, unmodified answer and opaque ID. They hide the method, task assignment, author appropriateness, source history and original outcomes. Reviewers might infer styles from the answer itself. [Inventory](REFLECTION_INVENTORY.json) · [Freezer](freeze_reflection.py)

## Review and scoring

Provide each reviewer only their JSONL packet, a copy of the blank response template, and the guidance below. Keep the original rendering or raw Markdown visible, including bold, emoji and signatures. Review the packet independently. Mark `yes` when the answer exhibits the specified attribute, `no` when it does not, and `uncertain` when the expression is too ambiguous to classify. Use the optional evidence field for the relevant phrase or a brief reason. A blank vote is unsubmitted. The task is occurrence or expression detection. Contextual suitability and factual support are different judgments.

The private custodian joins the votes after submission. The [analysis script](analyze_reflection.py) reports each reviewer's scores, exact binary consensus, disagreement, and Cohen's kappa on paired binary votes. It distinguishes uncertainty and blanks. It compares Qwen and consensus on the original common-score subset and also reports every valid original field separately. Report MR with and without nicknames, AAR with bold and non-bold strata, and full 48-task allocation bounds. Disagreement or missing responses remain unknown in consensus. Original Qwen fields are preserved.

This package has been frozen and tested with blank and synthetic local votes. No human labels or additional model scores have been collected. A separately qualified model can provide an automated robustness comparison under a distinct reviewer identity and report. It cannot supply human annotation. Source-grounding checks will use separate evidence packets and metrics. This phase used zero model requests and accessed no sealed data.
