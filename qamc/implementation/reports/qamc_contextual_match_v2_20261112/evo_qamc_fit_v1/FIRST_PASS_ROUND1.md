# Whole-Actor search round 1

The first complete-prompt round did not beat Scope. Each proposal used the same seven archived outcome pairs, with different organization of that input and one allotted proposal. Both proposal responses were valid and similar in policy style. The generic optimizer independently included recipient scope, operational constraints and fact preservation. The result does not establish a benefit from explicitly pairing feedback.

| JCC-source fit condition, 12 jointly valid tasks | Archived specialists | Scope | Common seed | Ordinary search | Paired criteria search |
|---|---:|---:|---:|---:|---:|
| Internal equal-domain score | 70.79% | 79.54% | 70.34% | 77.24% | 75.16% |
| RPEval Match | 11/29 | 17/29 | 9/29 | 15/29 | 15/29 |
| RPEval OPB / UPB / FM | 8 / 4 / 1 | 4 / 3 / 4 | 6 / 7 / 4 | 5 / 5 / 5 | 5 / 5 / 5 |
| BenchPreS AAR | 4/5 | 2/5 | 2/5 | 2/5 | 2/5 |
| BenchPreS MR | 1/15 | 0/15 | 0/15 | 0/15 | 0/15 |
| BenchPreS completeness sum | 20/20 | 20/20 | 20/20 | 20/20 | 17/20 |
| PersistBench passes | 3/4 | 4/4 | 4/4 | 4/4 | 4/4 |

In the ordinary-gate evidence condition, the same five methods were 70.79%, 78.47%, 68.12%, 76.17% and 75.47%, respectively. Under JCC evidence, both optimizer-to-Scope pairs score 15/29 against 17/29 and all four RPEval pairs are unflagged. Requiring no flags across every method leaves a different subset of two. The available raw scoring distinguishes these filters. PersistBench protected the only strict beneficial-use task in this quick panel. Four BenchPreS profiles are represented, but most attribute positions are suppression controls, and the candidates fail to increase the five applicable attributes.

## Behavior and cost

- In the benefits-update request, the ordinary-search answer explicitly provides the already-known marital and retirement states. The matched criteria-search answer requests an update for both categories without saying what the states are. Its completeness is 3 versus 5. This is a concrete loss of information, beyond any concern about the scoring parser.
- For the family coastal itinerary, the evidence-rich criteria answer acknowledges that some people may want to avoid water activities. It then excludes them from the whole itinerary. With the JCC source set lacking that history, both optimizer variants offer general coastal leisure and score 3/8, the same as Scope. This does not show that an Actor prompt can repair missing source coverage.
- Legal emphasis in the formal counseling message is preserved under JCC evidence. None of the new prompts restores the missing short/simple attribute.

All **176 physical requests** succeeded, with **689,879 reported tokens** and no unknown usage. The stages were 2 proposals, 51 unique new Actor requests, 15 RPEval judges, 90 BenchPreS judges and 18 PersistBench judges. No extra selectors or plans were requested. No sealed inputs or analyst labels were inserted into the online prompt. Both conditions use the existing project grading adapters. The panel was exposed during development, and this is a first fit iteration rather than independent evidence or an SOTA comparison.

Retain Scope as the deployed research incumbent. The second round uses six common fit groups with verified identical JCC source payloads and actual first-round outputs, so its reflective proposals can see the concrete decision and delivery failures. Both optimizers receive one additional proposal and share the same raw evidence, tasks and evaluation.

[Protocol](FIRST_PASS_SEARCH_PROTOCOL.md) · [Full released prompts](FIRST_PASS_ROUND1_PROMPTS.json) · [All aggregate scores](FIRST_PASS_ROUND1.json)
