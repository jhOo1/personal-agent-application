# PersistBench adaptive memory-policy search

Two search rounds on the same 12 exposed roots compared adding guidance inside the original PB_RUBRIC memory-use block with replacing that block. Both arms received identical development feedback within each round. Round two used real first-round outputs and scores, with identical marked excerpts to satisfy input capacity. The original task, memory, outer system prompt and Actor settings were fixed. The starting reference was archived PB_RUBRIC. The project grading adapter remains unchanged.

| Split | PB_RUBRIC | Append | Replace |
|---|---:|---:|---:|
| Search round 1 | 9/12 | 10/12 | 10/12 |
| Search round 2 | 9/12 | 10/12 | 10/12 |
| Source-disjoint development | 10/12 | 8/12 | 9/12 |
| Group-out SYC | 3/5 | 3/5 | 2/5 |
| Group-out CD | 4/4 | 2/4 | 4/4 |
| Group-out strict BU | 3/3 | 3/3 | 3/3 |

The two round-one arms both repaired the project template. In round two replacement also repaired the welcome email and regressed the public dinosaur exhibit, which again included a Flood explanation. Both modes tied their first-round search scores and protection counts, so both first-round policies were selected under the frozen tie rule. On the group-out split neither repaired the two baseline failures. Append introduced two cross-domain failures and Replace introduced one sycophancy failure. Keep PB_RUBRIC, and do not interpret the one pass difference between the new arms as a useful replacement advantage.

The first replacement policy reply used the field `text` instead of `policy`. A separately recorded recovery reused its exact value and evaluated only the previously unissued Actor requests. No proposal was regenerated. Search used 100 requests and 951,203 reported tokens, including recovery. Group-out used 48 requests and 445,797 reported tokens. All 148 transport requests succeeded. The group-out panel is relative to this search and contains previously exposed development data. No sealed data used. This is an adaptive two-round edit-space comparison, not an official GEPA reproduction or independent confirmation.
