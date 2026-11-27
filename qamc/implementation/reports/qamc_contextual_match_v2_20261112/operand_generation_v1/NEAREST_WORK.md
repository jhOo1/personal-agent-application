# Boundaries of the operand realization hypothesis

Rule-based realization of structured meaning is established prior work. Fang et al. transduce dialogue action/result graphs into context-free response grammars and use a pretrained generator to choose faithful, fluent text within those grammars. That setting supplies an executed program and its result. QAMC receives fixed historical text and a current request. The harder relation is whether a historical operand is appropriate for the current participant, time or event. A deterministic output path does not prove that relation. The current test gives the renderer a narrower role and compares it to equal-budget free editing on original end-user drafts. [Fang et al., Findings of ACL 2023](https://aclanthology.org/2023.findings-acl.351/)

Separating content planning from realization also has a substantial data-to-text literature. Moryossef et al. form a symbolic content plan and train a neural generator to realize it. QAMC RELATION retained a free Actor after source projection, and that Actor changed a historical state into a current assertion in an observed case. The new implementation closes only specific output actions so that a subsequent generator cannot make that transformation. Claims about a general advantage require actual output behavior and score gains over FREE. [Moryossef et al., NAACL 2019](https://aclanthology.org/N19-1236/) · [Observed QAMC relation failure](../bench_relation_compiler_v1/BEHAVIOR_READOUT.md)

## What the predecessor code already did

| Method | Actual executable allowance | Remaining gap |
| --- | --- | --- |
| DREW | Atomic replacement of uniquely matched draft substrings, plus a witness in the new text | The replacement string carries arbitrary model-authored relations. |
| TATR | Deterministic copy/drop, exact interpolation of literals, and atomic reassembly | WRITE and INSERT accept arbitrary text parts. |
| Decision DELTA | Original location, bounded length, single-line edits and source quote checks | EXTEND and REPLACE still accept arbitrary semantic content. |
| RELATION | Exact original fact clauses and an independently anchored query | A free-text action can embed an unsupported relation. The final Actor can also reinterpret a correct clause. |
| Operand | Predeclared query templates and complete recorded-event quotes, with source IDs and no later Actor | Retained draft assertions can still be wrong. Selecting a source or recipient action remains a semantic judgment. The choice-name slot controls optional presentation and cannot certify a new option. |

The proposed advantage is in controlling specific rendered relations under a real memory-use benchmark, with scope limits exposed by negative cases. It should not be presented as the first use of symbolic realization or as an end-to-end factual guarantee. A targeted reduction in incorrect relations can coexist with fewer useful alternatives, weaker personalization, or an incomplete deliverable. Those are measured separately in the frozen comparison.

[Predecessor DREW](../archive_edit_opportunity_v1/PROTOCOL.md) · [TATR](../transactional_reassembly_v1/assembler.py) · [Decision DELTA](../rpe_decision_delta_v21/delta.py) · [Current implementation](operand.py)
