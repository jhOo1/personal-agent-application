# RPEval paper Figure 14 fixed-answer crossover

Reconstruct the author paper's multi-preference Figure 14 prompt from arXiv v1's TeX asset, distinct from the short root repository template. Verify the asset hash. Retain the meaning, severity names and schema of Figure 14. Remove typesetting markup and supply the existing author evaluation fields between explicit delimiters. Figure 14 is public prose and contains placeholders and pseudo-JSON, not a byte-level request log. This is a paper-faithful reconstruction with an explicit serialization convention. The actual historical evaluation request and underlying provider are not authenticated.

Use the 12 exact exposed development pairs from the released short prompt check; both saved Qwen endpoints and the IPE-C routing are unchanged. GPT-4.1 alias, system message, model settings and output caps are inherited from that comparison. Never regenerate an Actor or overwrite previous grades. Macro and Micro are accepted only if both parse and agree for the correct original denominator. Fractions must report the original denominator; numbers may encode an exact proportion. Do not invent precision for rounded numbers or impute a failed grade. Keep the paper's FB/LF raw labels distinct from project OPB/FM.

Under the matched valid set, report the original detailed adaptation and Figure 14 side by side, including index denominators, Macro and Micro. This qualification is an analysis of the paper prompt on exposed data, not an official ranking or new method.

Restore the original QAMC checkout and its documented Python environment. Obtain the original asset without redistributing the prompt text:

```bash
curl -fsSL https://arxiv.org/src/2601.16621v1 -o /tmp/qamc-author-rpe-v1.tar.gz
tar -xOzf /tmp/qamc-author-rpe-v1.tar.gz boxes/mgen_evaluator.tex > /tmp/qamc-author-rpe-mgen.tex
python evaluate.py freeze /tmp/qamc-author-rpe-mgen.tex
python evaluate.py run /tmp/qamc-author-rpe-mgen.tex
python evaluate.py replay /tmp/qamc-author-rpe-mgen.tex
```

Primary source: RPEval paper v1 Figure 14, and the short code fixed at `0f8bce80`.
