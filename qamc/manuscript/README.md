# QAMC paper working draft

The [working PDF](paper.pdf) uses the official ACL style in preprint mode. The author field is a working-draft placeholder. [Editable source](paper.tex) · [References](references.bib)

The manuscript keeps the three benchmarks on separate scoring protocols. Its tables are from matched development comparisons. The completed PersistBench repeat-deployment result uses the project grader. An author-score bridge remains a separate, unrun evaluation. No unfinished experiment contributes a result to this draft.

| Evidence | Authoritative project report |
|---|---|
| RPEval released roster, matched external pipelines and both fixed answer paths | [Common comparison](../implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/COMMON_COMPARISON_CLOSURE.md) · [Exact three-path aggregation](../implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_two_endpoint_completion_v1/READOUT.md) |
| RPEval equal-rate controls and second backbone | [Equal-rate comparisons](../implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_rate_matched_controls_v1/READOUT.md) · [GPT-4.1 matched subset](../implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_second_backbone_v1/READOUT.md) |
| RPEval single-preference external comparison and actual B exposure in the multi-preference roster | [Single-preference bridge and exposure coupling](../implementation/reports/qamc_contextual_match_v2_20261112/rpe_single_endpoint_bridge_v1/READOUT.md) |
| RPEval explicit/implicit inputs and original memories | [Release identity and formats](../implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/RPE_RELEASE_IDENTITY_AND_FORMAT.md) |
| PersistBench comparisons, 49-pair allocation and caveats | [Selected GEPA comparison](../implementation/reports/qamc_contextual_match_v2_20261112/persist_selected_gepa_completion_v1/READOUT.md) |
| PersistBench repeated deployments and equal-cap mechanism check | [Completed three deployments](../implementation/reports/qamc_contextual_match_v2_20261112/persist_repeated_deployment_v1/READOUT.md) · [Equal-cap check](../implementation/reports/qamc_contextual_match_v2_20261112/persist_repeated_deployment_v1/EQUAL_CAP_LEGACY.md) · [Matched-cap utility and behavior](../implementation/reports/qamc_contextual_match_v2_20261112/persist_equal_cap_development_v1/READOUT.md) · [Historical utility controls](../implementation/reports/qamc_contextual_match_v2_20261112/persist_frozen_utility_review_v1/EXTENSION_READOUT.md) · [Two-wave equal-cap risk study](../implementation/reports/qamc_contextual_match_v2_20261112/persist_equal_cap_safety_v1/READOUT.md) |
| RPEval shared-Actor MemGate and language mismatch | [End-to-end comparison](../implementation/reports/qamc_contextual_match_v2_20261112/rpe_memgate_matched_actor_v1/READOUT.md) · [Count-matched language adaptation](../implementation/reports/qamc_contextual_match_v2_20261112/rpe_memgate_language_control_v1/WIDE_READOUT.md) · [Equal-count final answers](../implementation/reports/qamc_contextual_match_v2_20261112/rpe_memgate_equal_count_answer_v1/READOUT.md) |
| PersistBench released external selector | [Matched MemGate versus routed, empty and full history](../implementation/reports/qamc_contextual_match_v2_20261112/persist_memgate_matched_actor_v1/READOUT.md) |
| BenchPreS published-control adaptation and renderer comparison | [Raw/Selectivity/Gate](../implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/BENCH_RAW_COMMON_BRIDGE.md) · [Matched message generation](../implementation/reports/qamc_contextual_match_v2_20261112/bench_speech_act_renderer_v1/READOUT.md) |
| BenchPreS three-draw replication and missing bounds | [Final replay and receipt reconciliation](../implementation/reports/qamc_contextual_match_v2_20261112/benchpres_repeat_matched_v1/FINAL_READOUT.md) |
| BenchPreS non-bold evaluation sensitivity | [Same-answer census with GPT-4.1](../implementation/reports/qamc_contextual_match_v2_20261112/benchpres_repeat_matched_v1/NONBOLD_CENSUS_READOUT.md) |
| BenchPreS profile-disjoint realization replication | [Matched direct and content-first results](../implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/BENCH_GROUP_OUT_RESULTS.md) |
| Task-wise better full-history comparator and direct-generation demonstrations | [PersistBench joint control](../implementation/reports/qamc_contextual_match_v2_20261112/persist_repeated_deployment_v1/JOINT_CONTROLS.md) · [RPEval paired illustrations](../implementation/reports/qamc_contextual_match_v2_20261112/teacher_feature_actor_v1/RESULTS.md) · [Matched external methods](../implementation/reports/qamc_contextual_match_v2_20261112/teacher_feature_actor_v1/OPPONENTS.md) |
| Transfer of PersistBench selection to the RPEval history-on branch | [Two-draw comparison](../implementation/reports/qamc_contextual_match_v2_20261112/rpe_pb_on_transfer_v1/RESULTS.md) · [Actual exposed sources](../implementation/reports/qamc_contextual_match_v2_20261112/rpe_pb_on_transfer_v1/EXPOSURE.md) |
| Fixed Gate with two generators and three fresh draws | [Matched scores and decision](../implementation/reports/qamc_contextual_match_v2_20261112/bench_fixed_gate_actor_v1/RESULTS.md) · [Source-grounded case audit](../implementation/reports/qamc_contextual_match_v2_20261112/bench_fixed_gate_actor_v1/DRAW0_CASE_AUDIT.md) |
| Group-level score sensitivity | [Paired source stability](../implementation/reports/qamc_contextual_match_v2_20261112/paired_source_stability_v1/READOUT.md) |

See the [extended research draft](../implementation/reports/qamc_contextual_match_v2_20261112/paper_evidence_handoff_v1/CONDITIONAL_MEMORY_MANUSCRIPT_DRAFT.md) for additional ablations, paired denominators and evidence links. Private benchmark traces, sealed data and service credentials are outside this folder.

## Verify table values

Run `python3 check_evidence.py` in this directory. It checks the main numeric tables and selected quantitative claims against the public evidence. It does not read private case traces or dispatch any requests.

## Build

Run from this directory. Use a TeX Live installation with `latexmk`, pdfLaTeX, BibTeX, the common ACL dependencies and Times/Helvetica fonts. The build runs in an isolated directory and requires no tokens or benchmark data.

```sh
build_dir="$(mktemp -d)"
acl_rev=d5adc823ff0f80f98c80405ca0ab66c68e684409
cp paper.tex references.bib "$build_dir/"
for asset in acl.sty acl_natbib.bst; do
  curl -fsSL "https://raw.githubusercontent.com/acl-org/acl-style-files/$acl_rev/$asset" \
    -o "$build_dir/$asset"
done
(cd "$build_dir" && latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex)
cp "$build_dir/paper.pdf" ./paper.pdf
```

The [comparison and recovery status](COMPARISON_STATUS.md) records the strongest available references, official scorer gaps, and the next reproducible evaluations.
