# weave-team QA entity port: calls_merged -> calls_complete

Run date: 2026-07-07. Entity: weave-team (QA). Driver process from PR #7535,
executed sequentially smallest-first with per-project gates.

## Outcome

| metric | value |
|---|---|
| projects migrated | 55/55 |
| calls migrated | 6,584,171 |
| failed verify (untouched, no attach) | 0 |
| skipped (nothing to migrate) | 0 |
| total wall time | 6.3 min |
| orphan-end calls dropped (expected loss) | 26 |
| past-retention calls excluded (expected loss) | 0 |

## Timings

| step | p50 | p90 | max |
|---|---|---|---|
| fill | 0.6s | 5.46s | 53.12s |
| attach (per partition) | 0.36s | 0.44s | 1.79s |

## Per-project results (smallest first)

| project | calls | status | fill | attach total | partitions |
|---|---|---|---|---|---|
| inference | 1 | migrated | 0.7 | 0.38 | 1 |
| filter-long | 1 | migrated | 0.56 | 0.42 | 1 |
| repro-wb-23754 | 1 | migrated | 0.45 | 0.34 | 1 |
| josiah-projec | 3 | migrated | 0.73 | 0.34 | 1 |
| break-buf | 4 | migrated | 0.66 | 0.38 | 1 |
| test_josiah | 5 | migrated | 0.73 | 0.72 | 2 |
| tmob-fix | 5 | migrated | 0.53 | 0.4 | 1 |
| chance-test1 | 10 | migrated | 0.32 | 0.38 | 1 |
| quickstart_playground | 10 | migrated | 0.66 | 1.04 | 3 |
| scoring-load-oai-test10b | 20 | migrated | 0.36 | 0.37 | 1 |
| scoring-load-oai-test10 | 20 | migrated | 0.3 | 0.37 | 1 |
| 101-ops | 20 | migrated | 0.53 | 0.33 | 1 |
| audio-eval | 25 | migrated | 0.32 | 0.34 | 1 |
| realtime-idle-conversation-qa1 | 27 | migrated | 0.58 | 0.33 | 1 |
| dino-agent | 29 | migrated | 0.36 | 0.35 | 1 |
| chance-combine1 | 120 | migrated | 0.63 | 0.37 | 1 |
| retry-test | 144 | migrated | 0.32 | 0.34 | 1 |
| mike-audio-test | 258 | migrated | 0.76 | 0.77 | 2 |
| csbx | 345 | migrated | 1.47 | 1.99 | 5 |
| monitor-demo-2 | 364 | migrated | 0.35 | 0.34 | 1 |
| scoring-load-nano2 | 400 | migrated | 0.33 | 0.32 | 1 |
| scoring-load-nano1 | 400 | migrated | 0.37 | 0.35 | 1 |
| 2026-04-16_image-eval | 402 | migrated | 0.66 | 0.44 | 1 |
| evals | 434 | migrated | 0.64 | 0.34 | 1 |
| realtime-idle-conversation-qa | 560 | migrated | 20.63 | 1.41 | 2 |
| swe-polybench-evaluation | 710 | migrated | 0.73 | 0.38 | 1 |
| nicho-alerts-2 | 734 | migrated | 0.64 | 0.37 | 1 |
| nicho-alerts | 824 | migrated | 0.38 | 0.33 | 1 |
| eval | 1,202 | migrated | 0.33 | 0.39 | 1 |
| simple | 1,345 | migrated | 0.48 | 0.7 | 2 |
| monitor-demo | 1,490 | migrated | 0.6 | 0.35 | 1 |
| scoring-worker-load-test | 2,151 | migrated | 0.41 | 0.74 | 2 |
| buf-lots-123 | 4,724 | migrated | 0.6 | 0.36 | 1 |
| scoring-load-notrace-5k | 5,000 | migrated | 0.34 | 0.31 | 1 |
| brand-awareness-agent | 9,005 | migrated | 4.03 | 1.46 | 1 |
| scoring-load-b100-5k | 10,000 | migrated | 0.42 | 0.4 | 1 |
| scoring-load-nano5k | 10,000 | migrated | 0.38 | 0.35 | 1 |
| scoring-load-oai-5k | 10,000 | migrated | 0.38 | 0.37 | 1 |
| scoring-load-burst-rerun1 | 10,000 | migrated | 0.4 | 0.32 | 1 |
| wt-async-inserts-batch-10 | 11,002 | migrated | 0.73 | 0.39 | 1 |
| wt | 11,002 | migrated | 0.66 | 0.41 | 1 |
| attr-maps-bench-op | 13,750 | migrated | 0.47 | 0.35 | 1 |
| scoring-load-burst-rerun-10k | 20,000 | migrated | 0.48 | 0.37 | 1 |
| monitor-test | 29,460 | migrated | 1.15 | 2.27 | 6 |
| delete-timing | 33,312 | migrated | 0.58 | 0.34 | 1 |
| types-chance | 40,651 | migrated | 1.8 | 0.37 | 1 |
| wtypes | 100,010 | migrated | 1.4 | 0.52 | 1 |
| test-insert-logging | 103,342 | migrated | 2.74 | 0.29 | 1 |
| griffin-mock-prod-agent | 108,393 | migrated | 1.7 | 0.3 | 1 |
| fake-true-text-processing | 134,757 | migrated | 5.46 | 0.34 | 1 |
| wt-sync-inserts-batch-10 | 231,007 | migrated | 3.55 | 0.33 | 1 |
| swe-polybench-evaluation-parallel | 537,407 | migrated | 9.06 | 0.55 | 1 |
| test-multi | 1,135,277 | migrated | 53.12 | 2.2 | 2 |
| wt-sync-inserts | 2,002,004 | migrated | 25.71 | 0.34 | 1 |
| wt-async-inserts | 2,002,004 | migrated | 25.9 | 0.3 | 1 |
