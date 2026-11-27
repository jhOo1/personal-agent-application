# Does the history-aware switch beat the task-only switch?

Same actor endpoints and grading records for all decisions. Twelve distinct task requests, two different source histories per request. Identical query-only switches were reused within each pair. Source selection used task/UID hashes and distinct histories, without choosing by score. All tasks are exposed development cases.

|Subset|Tasks|Positions|Gate or endpoint|History ON|Match|OPB|UPB|FM|
|---|---:|---:|---|---:|---:|---:|---:|---:|
|all|24|126|query|2|69|9|50|36|
|all|24|126|memory|19|82|30|15|6|
|all|24|126|IPE-C|14|81|29|15|9|
|all|24|126|empty|0|66|7|54|37|
|all|24|126|full|24|85|30|11|6|
|unflagged|18|103|query|2|62|7|31|29|
|unflagged|18|103|memory|14|69|24|6|5|
|unflagged|18|103|IPE-C|10|68|24|6|7|
|unflagged|18|103|empty|0|59|5|35|30|
|unflagged|18|103|full|18|69|24|6|5|
|contains_C|13|83|query|1|38|6|40|33|
|contains_C|13|83|memory|13|47|26|9|6|
|contains_C|13|83|IPE-C|13|47|26|9|6|
|contains_C|13|83|empty|0|35|4|44|34|
|contains_C|13|83|full|13|47|26|9|6|
|only_B|0|0|query|0|0|0|0|0|
|only_B|0|0|memory|0|0|0|0|0|
|only_B|0|0|IPE-C|0|0|0|0|0|
|only_B|0|0|empty|0|0|0|0|0|
|only_B|0|0|full|0|0|0|0|0|

OPB, UPB and FM are project-adapted grader severity sums, not position counts. See metric availability in the paired-outcome audit.

Decision disagreements: 19. Physical gate calls: 36. Transport status: {'OK': 36}. Invalid decisions after successful transport: 0. Reported tokens: 31589. No new Actor answers or native grades. No human review. The original preflight stopped before dispatch because streaming usage was not requested; the corrected transport manifest is separate.

## Paired outcomes

History-aware versus query-only by task (Match): {'win': 10, 'loss': 2, 'tie': 12}

Complete matched task groups: 12 ; different history-aware decisions across their two histories: 3 ; group wins/losses/ties: {'loss': 2, 'win': 6, 'tie': 4}

Paired task denominators for severity sums and Match: {'Match': 24, 'OPB': 24, 'UPB': 24, 'FM': 24}

### Within-request discrimination (exploratory)

On complete groups, observed history-aware Match 82; expected Match 82.0 when its opening count stays fixed within each identical request and assignments of openings to histories are uniform. This diagnostic conditions on observed decisions and uses archived scores.

## Research decision

Keep the archived candidate. The history-aware gate beats the deployable query-only control on this panel but trails always-full. The independent contribution of assigning the openings to the correct histories within a task remains unestablished. In the creative-company interview task both histories switched to full, improving Match from 0 to 3 and 2 to 3 respectively. In a weekend parent–child activity request both also switched to full; one stayed at 5 while the other fell from 7 to 5. This identifies actual endpoint choices and their metric consequences; it does not attribute each grade movement to a specific sentence. All 13 C-bearing cases received full history under both IPE-C and the new gate. That proves delivery only. There are no B-only cases in the hash-selected panel. Continue reporting original benchmark protocols and the stronger fixed endpoints.
