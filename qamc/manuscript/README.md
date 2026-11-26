# QAMC paper working draft

The [working PDF](paper.pdf) uses the official ACL style in preprint mode. The author field is a working-draft placeholder. [Editable source](paper.tex) · [References](references.bib)

The manuscript keeps the three benchmarks on separate scoring protocols. Its tables are from matched development comparisons. The completed PersistBench repeat-deployment result uses the project grader. An author-score bridge remains a separate, unrun evaluation. No unfinished experiment contributes a result to this draft.

| Evidence | Authoritative project report |
|---|---|
| RPEval released roster, matched external pipelines and both fixed answer paths | [Common comparison](../implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/COMMON_COMPARISON_CLOSURE.md) · [Exact three-path aggregation](../implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_two_endpoint_completion_v1/READOUT.md) |
| RPEval equal-rate controls and second backbone | [Equal-rate comparisons](../implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_rate_matched_controls_v1/READOUT.md) · [GPT-4.1 matched subset](../implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_second_backbone_v1/READOUT.md) |
| RPEval explicit/implicit inputs and original memories | [Release identity and formats](../implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/RPE_RELEASE_IDENTITY_AND_FORMAT.md) |
| PersistBench comparisons, 49-pair allocation and caveats | [Selected GEPA comparison](../implementation/reports/qamc_contextual_match_v2_20261112/persist_selected_gepa_completion_v1/READOUT.md) |
| PersistBench repeated deployments and equal-cap mechanism check | [Completed three deployments](../implementation/reports/qamc_contextual_match_v2_20261112/persist_repeated_deployment_v1/READOUT.md) · [Equal-cap check](../implementation/reports/qamc_contextual_match_v2_20261112/persist_repeated_deployment_v1/EQUAL_CAP_LEGACY.md) |
| BenchPreS published-control adaptation and renderer comparison | [Raw/Selectivity/Gate](../implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/BENCH_RAW_COMMON_BRIDGE.md) · [Matched message generation](../implementation/reports/qamc_contextual_match_v2_20261112/bench_speech_act_renderer_v1/READOUT.md) |
| Group-level score sensitivity | [Paired source stability](../implementation/reports/qamc_contextual_match_v2_20261112/paired_source_stability_v1/READOUT.md) |

See the [extended research draft](../implementation/reports/qamc_contextual_match_v2_20261112/paper_evidence_handoff_v1/CONDITIONAL_MEMORY_MANUSCRIPT_DRAFT.md) for additional ablations, paired denominators and evidence links. Private benchmark traces, sealed data and service credentials are outside this folder.

## Verify table values

Run `python3 check_evidence.py` in this directory. It checks the four main numeric tables against three public aggregate reports. It does not read private case traces or dispatch any requests.

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
