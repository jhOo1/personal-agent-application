# Can repeated selection add genuinely new useful evidence?

Reconstructed exact selected evidence from archived route and selection receipts. For strict beneficial use, compare the first deployment with the newer capped repeat. For risk, compare the first two matched capped deployments. Verify original source indices and dated Actor request hashes. No new generation or judgment.

| Track | Allocated roots | Both selections recovered | Changed ordered exposure | Empty reopened by broader set | Union differs from both observed sets |
| --- | ---: | ---: | ---: | ---: | ---: |
| Strict beneficial use | 18 | 13 | 8 | 0 | 0 |
| Cross-domain | 19 | 19 | 4 | 1 | 0 |
| Sycophancy | 12 | 12 | 3 | 1 | 0 |

Five earlier utility selections are unrecoverable; the remaining 13 include one usable selection without a valid earlier grade. All 44 recovered pairs are nested. Both draws changed exposure on 15 roots, yet the union always equals one previously observed set. Across the 13 eligible utility pairs, merging into the first selection changes 4 roots and adds 6 entries; merging into the fresh selection does the same. It never reconstructs a genuinely different combined history. One fresh Qwen utility regression occurred with identical ordered evidence, and two accompanied changed exposure. Same-evidence roots also include one fail-to-pass and one unknown-to-pass. See the [earlier action traces](LOSS_RECURRENCE.md) for observed changes involving allergy and gardening.

## Policy replay

The replay chooses the saved answer of the larger selection if the second draw is a strict superset of the first; otherwise it uses the first. The protected variant additionally retains empty history whenever the first selection was empty. Neither rule reads grades. For matching exposures, preserve the original draw and its outcome. These are offline endpoint policies on exposed roots, not newly generated answers, and the risk figures below use one output per root rather than FR@3.

| Track and judge | First pass / fail / unknown | Second pass / fail / unknown | Either larger-set rule |
| --- | --- | --- | --- |
| Strict BU, Qwen | 11 / 1 / 1 | 9 / 3 / 1 | 11 / 1 / 1 |
| Strict BU, GPT-4.1 | 12 / 0 / 1 | 13 / 0 / 0 | 12 / 0 / 1 |
| Cross-domain, GPT-4.1 | 18 / 1 / 0 | 18 / 1 / 0 | 18 / 1 / 0 |
| Sycophancy, GPT-4.1 | 11 / 1 / 0 | 11 / 1 / 0 | 11 / 1 / 0 |

No paired binary win or loss relative to the first deployment. The two risk reopenings would still expose new historical material to the first answer path. Equal binary grades do not establish exposure safety. Five strict BU roots cannot be replayed from both selections and stay unresolved for the union policy. In particular this table does not replace the original 18-root utility deployment.

Do not promote repeated selection plus union on this evidence. Its online cost would include extra selection and a newly generated answer. The replay omits those costs and fixes each physical answer to its original draw. The relevant next distinction is whether a repair restores a task requirement and changes the delivered action, given the same amount of evidence and Actor budget. Generic source review previously recovered both traced utility losses too, while reopening beliefs in the risk examples. [Joint review comparison](../persist_joint_fact_review_v1/RESULTS.md)

Recompute from the private receipts with the exposure-recurrence subcommand of [inspect.sh](inspect.sh). [Public counts](EXPOSURE_RECURRENCE.json)
