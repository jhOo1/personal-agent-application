# Previously completed equal-cap GEPA comparison

The larger repeated-deployment experiment compares original deployed methods with the output-cap difference documented in the [wire audit](WIRE_PARITY.md). A smaller, already completed 12-case factorial supplies a distinct control. Both of its GEPA arms use Qwen 3.8 Flash, temperature zero, the same GEPA generation instructions, and a requested Actor cap of 8,192. They differ in whether full original history or the original selection is presented to the Actor. The archived GPT-4.1 Judge is an adaptation.

| Same archived tasks | Selected history pass | Full history pass |
|---|---:|---:|
| Cross-domain | 4/4 | 3/4 |
| Sycophancy | 3/4 | 2/4 |
| Strict beneficial use | 4/4 | 4/4 |
| Overall | 11/12 | 9/12 |

The paired comparison gives two wins, no losses, and ten ties. The offline checker verifies the source and exact generation request hashes, regenerates the two inputs using the same GEPA renderer, and verifies that their Judge requests match after replacing the evaluated answer. The archive is separate from the larger repeated-deployment study in protocol, but contributes records to the larger one-draw 49-case archive. Treating the two as independent studies would duplicate evidence. Generation times and upstream inference budgets also differ. No new deployment or scoring occurred in this audit. [Replay checker](equal_cap_check.py)

The scored wins come from a client essay strategy that incorporated an inapplicable historical argument under full history, and a public pollution metaphor that imported personal health history. The full factorial did not advance: it required at least two wins over both full-history GEPA and selected-history native, and the latter contrast had one net win. The four SYC cases also showed no descriptive GEPA-by-selection interaction. This comparison supports checking exposure under a matched cap without establishing broad fine-grained benefit or an interaction.
