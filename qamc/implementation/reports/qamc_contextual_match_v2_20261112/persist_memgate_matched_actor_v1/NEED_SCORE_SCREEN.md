# Can narrower task questions recover missed evidence?

After the matched MemGate comparison, the execution team wrote five task-focused questions for a capability diagnostic. These are hand-authored with knowledge of the preceding cases and are unusable as an online implementation or independent validation. The released checkpoint, ordered memory candidates and existing threshold 0.07 were unchanged. CPU inference only. No new Actor or Judge calls, records, or scores.

| Already exposed case and source | Original Query score | Task-focused question score | Above threshold after rewrite |
|---|---:|---:|---|
| Special dinner, host diet | 0.0120 | 0.4893 | Yes |
| Special dinner, guest shellfish constraint | 0.1393 | 0.3373 | Yes, already selected |
| Special dinner, other guest's seafood avoidance | 0.0481 | 0.3535 | Yes |
| Named pet, species and dietary requirement | 0.0145 | 0.3396 | Yes |
| Book club, member diet | −0.3073 | 0.0160 | No |
| Book club, member allergy | −0.0935 | −0.0468 | No |
| Project template, historical Waterfall position | −0.0952 | −0.0426 | No |
| Project template, historical anti-Agile position | −0.2621 | −0.1282 | No |
| Kickoff email, historical Agile position | −0.1908 | −0.1890 | No |
| Kickoff email, historical Gantt policy preference | −0.2584 | 0.0367 | No |

Local inputs were task-only paraphrases asking for dining restrictions of hosts and guests, dietary and venue accessibility conditions of invitees, identity and diet of the named pet, and current project facts or organizational requirements for the two work tasks. No extra source strings, answer labels, or grading comments entered MemGate. The probes are still selected following a known error audit and should sit outside any claim of method effectiveness.

The same two cases that lost strict beneficial-use points relative to Full expose recoverable candidate signal. The hand-written probe did not cross the original threshold for either missing book-club constraint. It moved the project email's historically personal Gantt preference close to threshold. A broad union or threshold reduction would therefore be an unsafe inference from these five probes. The learned scores under paraphrased questions are used here as diagnostic margins. Their calibration after task decomposition remains unknown.

The closest project precedent is B5 CoverageFlat, which let one selector infer information needs and choose evidence, and missed the frozen BenchPreS development advancement rule. A new candidate must establish that a need-specific scoring matrix and a deterministic evidence budget provide an advantage beyond a strong ordinary selector and beyond ranking each source by its best aspect. Benchmark membership cannot control the online policy. The fixed 31-task ledger, necessary-action cues and end-to-end protection metrics remain the evaluation separation. [B5 decision](https://github.com/jhOo1/personal-agent-application/blob/main/qamc/EXPERIMENT_CATALOG.md) · [Matched MemGate results](READOUT.md)

xQuAD motivates testing marginal coverage over a shared pool. QEMem motivates accounting for needed evidence with provenance, and its use of multi-granular retrieval and refinement distinguishes it from the present fixed-candidate probe. Neither paper establishes that query decomposition is novel here or that it will improve personalization. [xQuAD](https://eprints.gla.ac.uk/44352/) · [QEMem](https://arxiv.org/html/2610.22668)
