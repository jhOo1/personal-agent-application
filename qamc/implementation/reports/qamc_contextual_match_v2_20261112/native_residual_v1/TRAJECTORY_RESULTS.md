# Trajectory feedback and group-out development results

The proposals used the same twelve exposed search traces, with marked excerpts, and one proposal call per arm. Atomic mutation produced one rule and block mutation produced three. Each nonempty policy was evaluated unchanged on the search and group-out panels. Inference reused the native Actor request with only a system suffix. One proposal per method cannot estimate optimizer-level superiority.

| Split and metric | Archived reference | Atomic | Block |
| --- | ---: | ---: | ---: |
| Search RPEval Match | 19/31 | 22/31 | 14/31 |
| Group-out RPEval Match | 21/28 | 18/28 | 21/28 |
| Search BenchPreS AAR | 3/4 | 3/4 | 3/4 |
| Group-out BenchPreS AAR | 5/6 | 5/6 | 5/6 |
| Search PersistBench pass | 1/3 | 1/3 | 1/3 |
| Group-out PersistBench pass | 2/4 | 3/4 | 2/4 |

The group-out RPEval OPB/UPB/FM totals were 7/1/1 for reference, 9/2/0 for atomic, and 6/2/1 for block. Group-out BenchPreS MR was 0/4 across arms, with total completeness 10, 9 and 8 respectively on two common roots. Group-out RPEval and PersistBench common coverage was 5/5 and 4/4. Search coverage was 5/5, 3/3 and 3/4. The search-only RPEval gain came from a four-position increase on the child sleep-audio task and a one-position decline on the parent-child itinerary. Both original and atomic drafts already honor the no-ads and no-DIY requirements in those respective cases.

Neither policy met the deployment criteria. The atomic arm's RPEval search improvement reversed on group-out; its PersistBench gain is a single case. Benchmark-specific failure patterns should determine the next development intervention. Preserve the archived references and use real failure and protection cases before commissioning another shared strategy.

Proposal/search/group-out counts were 2/77/78 requests, with 28,002/265,000/275,930 reported tokens. Search had one known length failure. All group-out requests succeeded at transport; one BenchPreS root lacked a complete comparable grade. No retries. These results use the project scorer adaptations on exposed development groups. Sealed data were not used.
