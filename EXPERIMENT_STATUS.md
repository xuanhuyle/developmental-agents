# Experiment 0: status

Append-only. Newest entries at the bottom of the log.

## Implemented

- **Resource model.** Money is integer micro-dollars in a per-agent ledger: nothing creates money, allocation moves
  it, termination refunds it. Time is simulated in integer microseconds by a deterministic discrete-event engine,
  with START/COMPLETE events and a fixed event-class order. There is one `ComputeOption` (prices, latency model,
  effort, context capacity, concurrency). Information sources carry explicit fees and latencies: cheap SQL, slow
  documents. Each agent reads only from an inherited set of permitted sources.
- **Lifecycle actions.** WORK, QUERY, SPAWN (optionally followed by a wait for children, at no extra decision cost),
  MESSAGE, WAIT and TERMINATE. SPAWN and QUERY charges are all-or-nothing. A step reserve ensures no LLM step can
  overdraw. Agents are suspended rather than killed while their children hold money. Termination cascades, in-flight
  work is discarded, and lifetimes and deadlines are enforced.
- **Modes.** `single`, `central` (fixed decomposition), `router` (one-shot, for H2) and `developmental`. All four share
  one system prompt, which differs only in a single MODE RULES line, and every run records an equal-resource audit.
- **Task suite.** A deterministic synthetic world: 1 SQLite script and 15 documents. It has 15 tasks: 4 in class A
  (solo), 4 in class B (parallel), and 7 in class C (4 dependent, 3 shortcut "dissociation" tasks). There are also
  3 held-out pilot tasks. Ground truth is computed from fact tables.
- **Event log.** Append-only JSONL covering all 11 required event types. Every metric is recomputed from the log.
- **Fitness.** Raw metrics are stored without weights. Fitness is recomputed with the frozen weights, and exploratory
  rescoring is stamped as such.
- **Calibration.** It is LLM-free. Scripted oracle organizations (solo, fanout-k, atstart-k) run through the same
  runtime under an 18-point perturbation grid. They produce margin-stable S/P/ambiguous/I labels and a validity gate.
- **§8 evaluator.** A pure function: collapse, differentiation, twin and dissociation criteria, plus cost and quality
  contrasts with a two-level bootstrap. It also covers the validity conditions and the H2 router comparison.
- **Criteria check.** It feeds synthetic IDEAL, collapse and heuristic policies through the real evaluator to choose R
  and to show that the criteria can both pass and fail.
- **Pilot, freeze and run pipeline.** The pilot runs `single` and `central` only. The freeze does mechanical gate
  repair and writes `data/frozen.json`. The run is resumable, interleaved and retries infrastructure errors. The report
  writes markdown and JSON.
- **CLI.** `python -m devagents {calibrate, criteria-check, pilot, freeze, run, report, build-world}`.

## Tested (all without network)

Run `pytest -q`: 80 tests, all passing at the time of writing. They cover:

- **Accounting.** Conservation replayed from the log after every event. Spawning cannot create money. An allocation
  moves exactly from parent to child, and the spawn fee formula holds. Refunds equal the child's final balance.
  Unaffordable spawns are rejected whole. Every charge can be recomputed from the log. A small budget ends in
  `budget_exhausted` without overdraft. A policy that misreports usage raises `ReserveViolation`. Reports are charged
  to the sender.
- **Lifecycle.**
  - Division trades money for time.
  - Multi-source query latencies add up.
  - Both the continuation and an explicit WAIT wake exactly at the last report.
  - Messages are invisible before delivery.
  - Lifetime expiry discards in-flight work and notifies the parent.
  - Root termination cascades, with nothing starting after the end.
  - A deadline failure is scored at the deadline.
  - An agent with live children is suspended instead of killed.
  - Step-cap hits are logged.
  - Mode rules hold: `single` cannot spawn, `central` must spawn first under the fixed rule, `router` spawns only
    first.
  - The concurrency cap and permission inheritance hold.
  - Lineage can be reconstructed, and runs are deterministic.
- **Baselines.** The resource audits are identical across modes. Prompts differ only in the MODE RULES line. No regime
  or class names appear in prompts. Each block contains every mode, in a seeded shuffled order.
- **World.** The committed files match the generator. Facts are present in the sources and the SQL routes return the
  ground truth. Answers are unique and filters matter. Ids and questions carry no class cues. The grader and read-only
  SQL behave correctly.
- **Evaluator.** An ideal policy is supported. ALWAYS, NEVER, SPAWN-IFF-URGENT, SPAWN-IFF-MULTIDOC and RANDOM are each
  rejected by the criterion designed for them. A quality-losing policy is rejected by 4b. The validity checks catch
  missing runs and a failed manipulation check. The frozen calibration still verifies.
- **LLM path via a fake Anthropic client.** The request shape is correct: model, effort, JSON-schema output and
  max_tokens under the reserve. The transcript is append-only. A refusal becomes a charged invalid step. The full
  pipeline runs from runner to event logs to report (48 runs, 4 workers, resume). The pilot report and pilot
  statistics work.

- **Review regressions** (`tests/test_review_regressions.py`): one test per confirmed code-review finding, plus
  mutation-killing tests for rules that could previously be deleted without any test failing.

LLM-free commands also exercised: `calibrate` (the gate passes), `criteria-check`, and `freeze` (which produced the
provisional freeze below).

## Code review

A five-lens adversarial review (simulation and accounting, statistics, spec consistency, validity and API use, test
adequacy) ran before any LLM run, and a skeptic re-verified every finding. Result: 38 findings CONFIRMED, 1 PLAUSIBLE,
0 refuted. All were fixed or covered by tests; SPEC.md §11 item 15 lists them. The most consequential:

- the 20-step cap could be bypassed after a WAIT;
- concurrent SPAWNs could exceed the concurrency and agent caps;
- the pilot cost-variance estimate was biased low by about half, which would under-power R;
- reports counted stray runs outside the manifest;
- `verify_frozen` missed drift in calibrated values;
- the output schema broke prompt parity across modes;
- agents were never told the step-reserve rule.

## Not yet tested

- **Any real LLM call.** No `ANTHROPIC_API_KEY` was available in the build environment. This leaves untested:
  - acceptance of the structured-output JSON schema and `output_config.effort` by the live API;
  - real token counts, reasoning-token volume, the tokenizer ratio r, refusal rates, and the cost and time dispersion.
- **The pilot, the non-provisional freeze and the main run.** No LLM results exist, and none were fabricated.
- **The `--no-structured-output` fallback** against the live API.

## Known limitations

- **No incremental cells.** The calibration finds no cells where local, incremental decisions beat a one-shot router,
  so H2 cannot be positive by design (SPEC §10).
- **Few designed P cells.** Only the 4 class-B `urgent` cells are P. The dependent cross-source `urgent` cells are
  ambiguous across the perturbation grid.
- **Provisional constants.** They are tuned only against oracle assumptions: 150 reasoning tokens per step and r = 1.
  If the pilot measures values far from these, mechanical repair may move them further.
- **R = 3 is borderline.** The ideal policy is "supported" in about 82% of simulations against the 80% bar, at the
  default p = 0.9 and cv = 0.25. The pilot's measured accuracy and cost variance will likely raise R.
- **Declared model.** The latency model is declared, not measured. There is no prompt caching. There is one model and
  one prompt wording.
- **Conservative input bound.** The step reserve uses a 1000-token schema overhead and a bound of 1 token per 2
  characters. Very small child allocations can end in `budget_exhausted` earlier than a tighter bound would allow.
  Agents see prices and balances, not this internal bound.

## Recommended next experiment

1. **Run the protocol here:** pilot, freeze, main, report. Then append the verdict below.
2. **Add incremental cells**, where information discovered mid-task changes the optimal organization and cannot be
   cheaply re-derived by children. Examples: 16+ candidates of which ~6 qualify, or an expensive unstructured narrowing
   step. This lets H2 (local vs one-shot) become a real test.
3. **Only then** vary compute heterogeneity (cheap parallel workers vs one strong model) as a second resource dimension.

## Freeze record

| date | kind | sha256 of data/frozen.json | R | notes |
|---|---|---|---|---|
| (initial commit) | PROVISIONAL (no pilot) | a39cf404…9544f6 | 3 | gate passed with no repair steps; p = 0.9 and cv = 0.25 are defaults. Superseded |
| after code review | PROVISIONAL (no pilot) | 910bf202…dbb6f9 | 3 | the reserve disclosure lengthened the prompt; mechanical repair took 1 step (doc processing 0.100 → 0.105 s/token). `run` refuses this freeze |

## Log

- Implementation and LLM-free verification complete. No pilot or main run yet: no API credentials were available.
- Adversarial code review completed; all 39 findings addressed, tests grown from 53 to 80, provisional freeze redone.
