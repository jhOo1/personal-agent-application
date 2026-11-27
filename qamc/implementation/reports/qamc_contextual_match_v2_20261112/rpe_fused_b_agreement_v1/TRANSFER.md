## BenchPreS

Deployed veto formula applied to 48 exposed tasks. Existing changed-answer pairs were sought only in the settled asymmetric-fusion run. Score model: qwen3.8-flash.

{'changed/all': 10, 'changed_tasks': 10, 'exact_changed_pairs': 7, 'graded_changed_pairs': 5, 'tasks': 48, 'veto_applicable': 4, 'veto_inapplicable': 6, 'veto_positions': 10, 'veto_unlabeled': 0}

Source groups with at least one labeled applicable preference vetoed: 3

Applicable preference types vetoed: {'bold emphasis': 4}

Matched answer totals, original then veto: {"all": [{"aar_denominator": 7, "aar_numerator": 5, "mr_denominator": 18, "mr_numerator": 2, "n": 5, "task_completeness": 21}, {"aar_denominator": 7, "aar_numerator": 4, "mr_denominator": 18, "mr_numerator": 0, "n": 5, "task_completeness": 25}]} 

## PersistBench

Deployed veto formula applied to 58 exposed tasks. Existing changed-answer pairs were sought only in the settled asymmetric-fusion run. Score model: gpt-4.1.

{'changed/beneficial_memory_usage': 4, 'changed/cross_domain': 9, 'changed/sycophancy': 3, 'changed_tasks': 16, 'exact_changed_pairs': 10, 'graded_changed_pairs': 8, 'tasks': 58, 'veto_positions': 27}

Matched answer totals, original then veto: {"beneficial_memory_usage": [{"failure_release": 0, "failure_release_n": 1, "failure_strict_utility": 0, "failure_strict_utility_n": 1, "n": 1}, {"failure_release": 0, "failure_release_n": 1, "failure_strict_utility": 0, "failure_strict_utility_n": 1, "n": 1}], "cross_domain": [{"failure_release": 2, "failure_release_n": 5, "failure_strict_utility": 2, "failure_strict_utility_n": 5, "n": 5}, {"failure_release": 3, "failure_release_n": 5, "failure_strict_utility": 3, "failure_strict_utility_n": 5, "n": 5}], "sycophancy": [{"failure_release": 1, "failure_release_n": 2, "failure_strict_utility": 1, "failure_strict_utility_n": 2, "n": 2}, {"failure_release": 2, "failure_release_n": 2, "failure_strict_utility": 2, "failure_strict_utility_n": 2, "n": 2}]} 


## Decision

Reject the disagreement veto as a common suppress rule. On the archived RPEval audit all 143 veto positions were author A; on BenchPreS four of ten are explicitly applicable, in three profile groups, all requesting emphasis with bold text. In the five exact graded BenchPreS pairs this trades one appropriate realization for two fewer inappropriate realizations and higher completeness. On PersistBench the exact graded subset adds one failure each in cross-domain and sycophancy; the sole paired strict-benefit task passes under both policies. No item-level ground truth is inferred from PersistBench task outcomes. These small opportunistic intersections are conditional on availability, evaluated with project adaptations. They cannot estimate a universal incompatibility between benchmarks or guarantee that any single demotion caused a score change. No new requests, retries, or sealed data.
