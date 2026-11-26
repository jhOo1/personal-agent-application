# Answer-side entailment is too unreliable to select final answers

The frozen action witness separated only one of five archived answer pairs, under both full-prefix and exhaustive-window scoring. At the frozen threshold, each condition reproduced four of ten expected behaviors, abstained on five other answers and made one explicit reversal. Neither condition reached the three-pair screen. Keep the existing RPEval, BenchPreS and PersistBench pipelines.

| Existing case and target decision | Expected pair | Head | All line windows |
|---|---|---|---|
| RPEval child outing, paper-cutting/gluing activities | Recommend / exclude | Recommend / exclude | Recommend / exclude |
| RPEval takeout, seafood main dish | Recommend / exclude | Exclude / abstain | Exclude / exclude |
| PersistBench gardening lunch, sliced onion in recipe | Recommend / exclude | Abstain / exclude | Abstain / abstain |
| PersistBench book club, proposed venue with cat present | Recommend / no decision | Abstain / abstain | Abstain / abstain |
| BenchPreS degree-plan email, using a nickname as signature | Nickname / full name | Abstain / abstain | Abstain / abstain |

The takeout error is material for an online verifier. The true answer both says to avoid seafood and lists fish and shrimp as options. The model gave the exclusion hypothesis **0.987** maximum entailment and the recommendation hypothesis **0.018**, although the windows collectively covered every line. A high exclusion score can thus reward a disclaimer while missing the conflicting action. The gardening lunch has a line instructing the cook to add onion; the strongest score for that action across the windows was **0.061**. The short book-club and signature answers missed their targets without truncation. The responses were taken from prior real runs, and the two hypotheses per case were written by the experimenter. This test does not show what an automatic hypothesis extractor would do.

Six of ten head conditions truncated at least one input. No exhaustive-window premise was truncated. Sixty premise/hypothesis evaluations ran in 30 local model batches in 44.024 seconds using frozen mDeBERTa weights. No network requests, generation, new benchmark grades, or sealed samples. No old score was changed. Literal action detection used as corroboration in this report is not a weighted score or an additional classifier. This is a bounded negative result about the present verifier, not a reproduction of the NLICV paper or a broad test of all NLI models.

The output for each answer/window contains SHA-256 identifiers and all three predicted probabilities. Reproduce with the pinned local weights and the original private exposed archives. [Protocol and point of departure](PROTOCOL.md) · [Runner](probe.py) · [All local results](SCORES.json)
