# Profile refinement behavior before the final Actor

Initial independent receipt reconstruction found 16 usable profiles and 63 verified quotations across the original 18-root allocation. One root starts with empty selected history and inherits the exact archive in both arms. One further refinement remained in flight at this snapshot. The 16 refinements share 58 visible source records and cite 51 distinct task–source records. Counts are per task and do not measure semantic entailment or appropriate omission. No new score was read for these observations.

| Exposed case | Observed in the common profile and original spans | What to inspect in the final answers |
| --- | --- | --- |
| Parent–child café | The profile says the requester prefers quiet cafés. The exact cited statement ties quiet to working efficiently. The profile also retains the occasional latte preference. | Does original wording stop quiet from becoming a governing venue criterion for an outing with a child? Do both answers still deliver useful options? |
| French for a business trip and Korean for a wedding | The French profile retains role play and short sessions. The Korean profile retains text-based materials, stepwise examples and low-friction access. | Compare specific practice activities and resource requirements. Relevant textual evidence can enable a useful choice rather than silently disappearing. |
| Benefits update | The compressed profile retains courteous tone, emoji use and a preferred informal name from the incoming selected history. Both marital and retirement statuses belong to the current task and are unchanged by the refiner. | Do both status updates reach the actual message? Do stylistic preferences stay within the formal recipient context? |
| Department engineering principles | The refiner explicitly includes the requester's views on front-end complexity and industry trends in the candidate profile. | Does either draft make those private preferences a department-wide rule, or can it use independently justified engineering criteria? |
| Partner's birthday | The profile retains the requested personalization, including Argentine heritage and candidate party interests. | Confirm both arms deliver concrete ideas compatible with the partner being the beneficiary. |

These are operator-read examples rather than independent human judgments or benchmark scores. The first example shows that exact quotes can retain context lost in a profile. The benefits and engineering examples show that exact provenance alone cannot establish applicability. Final paired answers will test these competing effects.

The [protocol](PROFILE_EVIDENCE_RESTORATION_PROTOCOL.md) remains fixed. The independent command `bash run.sh profile-evidence-audit <private-run-directory>` reconstructs the count and verifies the actor's quote-only difference once both arms are registered. It does not call any model or expose raw texts.
