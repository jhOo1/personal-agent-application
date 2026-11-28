# The two planning strategies respond differently to selective exposure

Forty exposed development tasks were assigned to each cell. The original task, facts, planner and final Actor setups were fixed within exposure and instruction contrasts. The selected-history rows reuse Self-ReCheck's ordered sources at both steps. One task retained all candidates and reuses both exact full-history outcomes. Thirty-five tasks have valid scores in all four cells.

| Four-cell common results | Full generic | Full actions | Selected generic | Selected actions |
|---|---:|---:|---:|---:|
| RPEval Match, 12 tasks | 29/69 | 31/69 | 27/69 | 29/69 |
| RPEval OPB / UPB / FM severity | 23 / 11 / 6 | 28 / 10 / 6 | 26 / 10 / 5 | 27 / 7 / 5 |
| BenchPreS appropriate preference realization, 11 tasks | 11/20 | 14/20 | 13/20 | 10/20 |
| BenchPreS misuse | 13/35 | 21/35 | 4/35 | 7/35 |
| BenchPreS task completeness | 48/55 | 48/55 | 51/55 | 51/55 |
| BenchPreS nonbold AAR | 6/14 | 8/14 | 10/14 | 7/14 |
| PersistBench cross-domain passes, one deployment | 2/4 | 4/4 | 4/4 | 4/4 |
| PersistBench sycophancy passes, one deployment | 1/4 | 2/4 | 1/4 | 1/4 |
| PersistBench strict beneficial-use passes | 4/4 | 4/4 | 4/4 | 4/4 |

On the common panel, changing the planner from generic to action-based increased the frozen development macro by 8.43 points with complete history. The same change decreased it by 1.65 points with selected history. The difference between those gains is −10.08 points. Its full-assignment missing-score range is −18.48 to −0.57 points. RPEval's common Match interaction is zero. BenchPreS loses three legitimate nonbold attributes when moving from selected generic to selected actions. Each of those three is for neutral or objective expression. PersistBench loses the prior positive contrast between generic and actions. The same three PersistBench tasks fail under both selected planners, including the dog-selection case at severity four.

These are one-deployment development estimates from separate batches. The missing-score interval addresses score coverage, not statistical sampling or temporal variation. Even on the selected history, action instructions can make output worse for desired expressions. At the same time, the filtered action cell has the fewest RPEval underuse marks. Preserve those distinct trade-offs for subsequent mutation.

The all-policy intersection ranks the task-only plan with selected final history highest among the tested single unified programs at 68.51%. Selected generic is 65.21%, task-only with full history 66.48%, and selected actions 63.56%. The archived specialist combination is 73.27% on that same set of tasks. Cross-method tables are available with pair-specific common sets and full assigned bounds. This is no published rank.

The two new arms added 340 physical requests, including 337 successful responses, two planner length stops and one RPEval score delivery-unknown. The report preserves these outcomes. Reported usage was 1,129,956 tokens. The next test has begun from the selected-final-history task-plan parent, preserving all 40 inherited inputs and modifying only the final instruction. The offline proposal supplies two general instructions. Both passed checks for structural validity and detectable copying or benchmark markers. [Four-cell contrasts](FACTORIAL.json) · [All-policy comparisons](WITH_SELECTED_PLANNING.json) · [Offline feedback selection](FACTORIAL_FEEDBACK_COUNTS.json)
