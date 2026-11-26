# Input coverage of the released MemGate encoder

The frozen author weights use all-MiniLM-L6-v2, which its model card labels English. The 295 verified queries are all predominantly Han characters. Under the pinned tokenizer and its actual 256-token SentenceTransformer limit, excluding special tokens, the false appearance of coverage can be measured directly.

| Frozen input | Count | Unknown / visible input tokens | Majority unknown | Truncated texts |
| --- | ---: | ---: | ---: | ---: |
| Query | 295 | 5,951 / 9,514 | 281 | 0 |
| Retained original source | 1,248 | 114,381 / 172,502 | 1,247 | 547 |
| Omitted original source | 324 | 42,217 / 64,078 | 324 | 236 |

The check reads frozen task inputs, tokenizes each without special tokens and counts the unknown ID in the prefix available at the encoder limit. The selector's original output is unchanged. These figures audit how much input reaches this specific tokenizer and do not estimate which source-level decisions would change under a language-matched representation. They limit the scope of any judgment about learning-based admission in general. The active comparison uses the released stack and therefore reports the performance of its direct adaptation. A separate translation control could investigate the mismatch without changing original text in the Actor, but the diagnostic introduces no new comparator.

Independent of grades, the selector passes 998 of 1,258 verified author-A positions, 122 of 155 B and 128 of 159 C. It exposes some history on 115/120 all-A tasks. This is a fixed exposure observation; the RP use policy can still affect realization. Under the current budget there were zero cloud calls for both audits. [Selection counts](SELECTION_AGGREGATE.json) · [Tokenizer outputs and pins](ENCODER_COVERAGE.json) · [MemGate paper](https://arxiv.org/abs/2606.06054) · [Encoder model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
