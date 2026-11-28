# Deletion compacts two messages without recovering the target preference

**The whole-sentence deletion method does not advance.** It shortened two messages and left every adapted score unchanged. Full rewriting earned two additional appropriate uses but lost two completeness points. Keep Strong Gate as the deployable reference.

| All eight common exposed tasks | AAR | Non-bold AAR | MR | Task completeness | Words |
|---|---:|---:|---:|---:|---:|
| Archived Strong Gate | 11/15 | 4/8 | 0/25 | 37/40 | 585 |
| Full rewrite, shared proposal | 13/15 | 6/8 | 0/25 | 35/40 | 536 |
| Whole-sentence deletion, shared proposal | 11/15 | 4/8 | 0/25 | 37/40 | 572 |

On the four frozen brevity misses: Strong Gate 0/4, full rewrite 2/4, deletion 0/4. Both variants preserved brevity scores on the two already fulfilled cases. Two abstention controls reuse the old answer. This is an exposed, profile-concentrated comparison using the unchanged project Qwen adaptation and zero independent human reviews.

## Actual message differences

- **Tax discrepancy, b22cff4a.** No complete eligible optional sentence was available. Full rewrite shortens the opening and removes the explicit request to review the records, while retaining the request for a resolution. Brevity changes to followed and completeness drops 4 to 3. Several details cited by the judge were already absent from the original. Those should not be assigned to the rewrite.
- **Specialist consultation, 54177376.** Full rewrite abbreviates blood pressure and drops the referring clinician attribution, while retaining the appointment request, clinical values and medication adherence. Brevity changes to followed, completeness stays at 5. The referral detail was present before and its loss shows that an unchanged score cannot certify content preservation. The deletion proposal was empty.
- **Other tax message, 9548a3d5.** The deletion removes only a thank-you sentence and preserves completion 5. The complete rewrite also retains measured brevity but drops one completion point. The evaluator criticizes the scope of the requested correction; it does not independently prove that any single textual change caused the drop.
- **Rental history, 00b95210.** Deletion removes a generic opening that repeats the subject line. Existing facts and the actual request remain. Both new variants still miss brevity and stay at completeness 3. This distinguishes reducing word count from changing the measured expression attribute.

The literal checks follow the general idea of separating verifiable constraints from subjective quality in [IFEval](https://arxiv.org/abs/2311.07911). The experiment is neither an IFEval replication nor a semantic guarantee. Its data indicate that the four known misses are not addressed by stripping only redundant complete sentences. Whole-answer rewriting has one local measured gain with unchanged completeness, but it also loses known content. A useful successor needs a way to simplify while retaining original semantic details, and should be tested outside the one profile that contains all four misses.

**54 successful physical requests**, 6 shared proposals and 48 scorer requests, **32,678 reported tokens**, no unknown usage and no retries. Four local contract checks passed for eligible text, preservation, no-op and invalid deletion. A pre-dispatch lookup failure was corrected by taking the selected view from the archived Gate record instead of assuming a source field in its flat Actor message. No request preceded that fix. No existing grade or sealed task changed.

[Protocol](PROTOCOL.md) · [Complete prompt and implementation](trial.py) · [Paired replay and ledger counts](SUMMARY.json)
