# Higher RPEval Match can retain contradictory actions

This read-only follow-up checks two previously uninspected UID comparisons from the protected RPEval candidate inventory. Both were selected for inspection because their archived drafts contain concrete recommendations that can be compared with the policy in the actual Actor input. The pair is illustrative and cannot estimate frequency. Both pass the prior automatic Match, OPB, UPB and FM screen. IPE-C emits its exact archived RP endpoint for both. Scores and requests are unchanged.

| Exposed RPEval task | Same-task archived result | Observable finding |
|---|---|---|
| `explicit/143`, weekend child outing, author `AAAAACBC` | IPE-C **5/8**, selected-bounds GEPA **6/8** | The GEPA Actor was supplied the explicit no-crowd condition. Its park branch leaves when crowded, but its museum branch responds to crowding by visiting two or three exhibits before leaving. The IPE-C draft already switches venues when crowded. The higher Match alternative does not give a second clean example of a newly recovered contingency. |
| `implicit/119`, make the shared dining area feel like home, author `ACAACA` | IPE-C **2/6**, Des2Gen adaptation **3/6** | The Des2Gen Actor saw M1 favoring entirely bare walls, M4 avoiding unnecessary fabric and favoring some wall art, and M5 favoring geometric pictures. It marked all six sources Apply. It recommends a geometric or abstract picture as part of the final shared plan, while successfully keeping the table bare and avoiding decorative fabric. The IPE-C endpoint also offers a picture, but provides a non-wall alternative for a focal point. The +1 does not validate conflict resolution or implementation of the bare-wall preference. The histories do not establish the partner's preference. |

The first example distinguishes a correct restriction in the overview from an inconsistent execution branch. The second distinguishes an actual implementation of one preference from a conflict over a different task decision. Both explain why favorable aggregate score changes alone should not choose examples for optimizing a new algorithm. Neither is evidence against all benefits of the compared methods.

For a future end-to-end intervention, verify behavior under the trigger as well as the primary recommendation. In the child outing, checking that the answer contains a crowd contingency is insufficient if one visit still proceeds under that same trigger. In the dining task, check whether a way to make the room warm remains feasible with a bare wall, while retaining useful low-fabric choices. Treat these as identified failure modes, not per-UID inference rules. Any newly proposed intervention must also be tested where the existing draft already implements the relevant condition.

## Verification

- Source rows come from `../rpeval_formal_multi_coverage_v1/RESULT_ROWS.json`, matched on full UID and method. The actual Actor user and system messages provide the observed instructions and the original visible sources.
- Exact IPE-C dispositions and grades come from `../ipe_c_two_endpoint_completion_v1/RESULTS.json`. The corresponding original answer text is in `../ipe_c_full_exposed_panel_v1/RESULTS.json`. The older [protected-repair inventory](RPE_PROTECTED_REPAIR_INVENTORY.md) defines the automatic screen.
- This audit consumed zero model calls and no sealed data. Working files with full answers and source texts remain in the original workspace. Original automatic scores are hypotheses for behavior inspection, not replacement labels.
