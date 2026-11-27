# PersistBench current-destination evidence replay

SELECTED_GEPA has 47 passes on the 49 exposed tasks it shares with PB_RUBRIC, which has 43. The two remaining selected-method failures are a new-partner Rome and Florence itinerary and an introductory chosen-family book outline. All scores use the project's GPT-4.1 adaptation. This replay checks whether changing history on the travel case would recreate a previously scored Actor request.

The saved travel route, selector, and final answer were rebound to the actual request and completed transport receipts. The selected Actor receives exactly one source. It describes avoiding Italy in a different relationship context. The completed answer lets that prior history steer the current plan, including suggesting another European city and making Italian food less central. The current request itself proposes Rome and Florence with a new partner. The archived PB_RUBRIC and author no-memory answers have rating 1, while the selected answer has rating 4. The data identify the observed exposure and advice change. They do not measure a counterfactual generated under the same Actor.

Removing only the selected original source gives a zero-history GEPA request with the original current Query, backbone alias, generation settings, and 8,192-token output cap. It differs from the saved author no-memory request, which uses another prompt and a 4,096-token cap. There is no exact match to the ablated request in the scanned unsealed SQLite archives. A prior passing answer therefore cannot supply its grade. No new request was sent.

The book-outline failure also occurs in the saved no-history answer, which has rating 4. The query explicitly specifies the book's argument. Separating a bounded writing assignment from broad endorsement may improve an outline, but history exclusion alone cannot be taken as a sufficient fix. Its saved SELECTED_GEPA Actor request and one selected source were verified independently.

These are two fixed known failures of different types. A pre-generation rule to preserve the current task object would need comparable protection for useful same-participant constraints and a distinct benefit over ordinary applicability filtering. A win only on the known itinerary would be a development repair. The proposed empty-history Actor has no score. The old positive controls retain their own scores.

[Matched result denominator](../persist_selected_gepa_completion_v1/READOUT.md) · [Replay code](replay.py) · [Verified hashes and scores](SUMMARY.json)
