# Frozen IPE-C history Actor answer-pool qualification

The archived candidate pool did not qualify the proposed learned-critic experiment. It contains different complete answers, but the execution-side comparison did not identify two source groups with demonstrated restoration of an already visible legal soft preference and simultaneous task and constraint protection. No IF-CRITIC, ordinary critic, Actor or benchmark Judge ran. No old scores changed.

## Release assets and task contract

IF-CRITIC has published MIT-labeled generative weights based on Qwen2.5-14B-Instruct and Chinese checklist inference. Its original interface takes an instruction, a response and a checklist. The authors train for constraint-level instruction following. Treating soft preference scope as checklist evidence and using the model to select complete answers would be an adaptation. The project has not tested that capability, and it cannot claim this model failed. [ACL paper](https://aclanthology.org/2026.acl-long.1147/) · [Released weights](https://huggingface.co/thu-coai/IF-CRITIC-14B) · [Pinned inference entry point](https://github.com/thu-coai/IF-CRITIC/blob/df219e253ffc26e7df60c72927e2523dd32b9256/critique_generation/if_critic_inference.py)

P-GenRM also has published weights, but the author example derives personalized scoring from past chosen/rejected pairs. The RPEval requests in this audit contain source history and predicted use classes, with no actual chosen/rejected user history. Inventing such records would change the task contract. [P-GenRM paper](https://arxiv.org/abs/2602.12116) · [Pinned author example](https://github.com/Tongyi-ConvAI/Tongyi-Character/blob/e7291e938986e79ab183163d919535cce1b32fcb/Character-GenRM/inference/single_inference.py)

## Exact-answer inventory

Start with the same 300 already-exposed RPEval tasks from the endpoint archive. Keep successful IPE-C history requests with at least one predicted B whose exact source is present. Verify the canonical Actor payload hash and the archived IPE-C answer hash. Query local development SQLite receipts by those exact request digests. Compare complete request objects including the Actor alias, history and ordering, policies, and all request settings. Count unique answer text by digest, exclude explicit length termination, and retain the frozen reference answer. Shared source groups and near-duplicates are not independent opportunities. Author labels are joined only to audit this retrospective inventory.

| Author-label slice | Eligible | Distinct complete same-request candidate | Also has visible author-B source predicted B |
|---|---:|---:|---:|
| All A | 10 | 2 | 0 |
| Only B | 6 | 2 | 1 |
| Contains C | 114 | 25 | 12 |

Of the 29 tasks with distinct alternatives, 13 have a visible author/predicted B source and span 12 conservative source groups. Task-only endpoints cannot supply exact history candidates. A changed Actor alias or a different sources list also fails the exact-identity condition.

## Behavior screen and stop decision

The operator inspected the source-conditioned action differences in the 13-task candidate slice, with no independent human review. This is an eligibility screen, not a revised rating or proof that every pair is behaviorally equivalent.

- In the sleep-audio task, the two drafts both turn the visible soft preferences into actual meditation and gentle piano or guitar suggestions. Both offer ways to reduce scrolling. Their order and implementation details differ.
- In the creative-company interview task, both drafts operationalize the comfort preference with loose but structured clothing and a small colorful accent. The later example outfit improves concreteness, without recovering a previously absent preference.
- In the Xi'an family day trip, both drafts recommend natural environments and specific local foods. The alternative changes the venue and dishes. The previously published counterfactual contingency involves a different candidate-generation contract and is not an exact-wire repetition.
- In the Yunnan family trip, a recovered alternate makes the mushroom exclusion explicit, while the baseline and alternate both offer local foods. This is a potential hard-constraint repair under the same request. It does not demonstrate a soft-B repair, and we do not independently certify restaurant ingredients.
- In the Qingdao trip, both drafts give non-seafood local options and a family seaside itinerary. The alternate elaborates the hard dietary protection and adds more options. The archived soft preference does not establish that a shared meal or itinerary must follow those additions.
- In the remaining cases, the differences include optional ambience, route or dish variants, and emphasis in an existing task action. The same-request dinner, decorating, colleague meal and family gathering pairs do not supply a confirmed second source for soft-B rescue.

The jazz/folk trial-class observation from the older retained-B report compares two methods with different full contracts. It cannot qualify this candidate pool. The stop condition concerns available same-request candidate supply, before evaluator capability or ranking can be measured. All 13 private review packets stay with the source archive. The public manifest includes only identifiers and counts. [Exact inventory](INVENTORY.json) · [Previous same-route comparison](../native_residual_v1/RPE_FIXED_ROUTE_ACTOR_CASE_AUDIT.md) · [Earlier retained-B audit](../retained_b_realization_v1/READOUT.md)
