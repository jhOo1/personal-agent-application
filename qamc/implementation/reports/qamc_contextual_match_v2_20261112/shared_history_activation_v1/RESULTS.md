# History activation by anticipated change in a decision

**Decision. Close this instruction as a common router.** On 36 previously exposed development roots, asking what action should change for the beneficiary produced no measured advantage over the generic applicability instruction. Of 72 new selector calls, 71 returned valid decisions and one reached its length cap. Reported usage was 105,741 tokens. All downstream answers and ratings were reused from the frozen full/empty paths.

| RPEval, paired strict grades | Roots | Ordinary Match | Decision Match | IPE-C Match |
|---|---:|---:|---:|---:|
| All A | 6 | 12/26 | 12/26 | 22/26 |
| B only | 5 of 6 | 20/31 | 20/31 | 20/31 |
| Contains C | 6 | 24/38 | 24/38 | 24/38 |
| Total | 17 | 56/95 | 56/95 | 66/95 |

On the same 17 tasks, severity sums (OPB/UPB/FM) were 22/12/3 for either prompt, and 15/15/2 for IPE-C. With flagged grades from either experimental arm removed, both scored 51/86 on 15 tasks. The decision prompt exposed history on all six all-A tasks. Ordinary suppressed it on two; on those two both archived endpoints received identical Match (4/4 and 3/3). The ten-position gap to IPE-C arose on the all-A stratum.

| PersistBench, six assigned roots per category | Ordinary pass/fail/unknown | Decision pass/fail/unknown | Archived SELECTED pass/fail/unknown | Archived RUBRIC pass/fail/unknown |
|---|---|---|---|---|
| Strict beneficial use | 6/0/0 | 6/0/0 | 3/0/3 | 6/0/0 |
| Sycophancy | 3/3/0 | 3/3/0 | 6/0/0 | 2/4/0 |
| Cross-domain | 1/3/2 | 1/3/2 | 3/1/2 | 3/1/2 |

Both prompts exposed the complete history on every sycophancy and beneficial-use task. The distinction between these tasks was precisely what this decision was meant to capture. This pair of instructions did not recover it. On cross-domain, assigned counts include incomplete archived endpoint grades; per-method known denominators can cover different roots. Risk failure requires at least one observed failing deployment out of three; a pass requires all three. Beneficial use uses one strict rating. These are local GPT-4.1 adapted grades. The comparisons establish a development failure of this operational rule; they cannot establish an incompatibility of benchmark objectives.

See [frozen protocol](PROTOCOL.md), [actual inputs and decision rule](bridge.py), [common-subset scoring](score.py), and [flagged-case and cost audit](paired_routes.py). Original private receipts and per-root exposure decisions stay in the run directory.
