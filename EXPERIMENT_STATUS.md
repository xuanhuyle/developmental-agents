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

Run `pytest -q`: 109 tests, all passing at the time of writing. They cover:

- **Accounting.** Conservation replayed from the log after every event. Spawning cannot create money. An allocation
  moves exactly from parent to child, and the spawn fee formula holds. Refunds equal the child's final balance.
  Unaffordable spawns are rejected whole. Every charge can be recomputed from the log. A small budget ends in
  `budget_exhausted` without overdraft. A policy that misreports usage raises `ReserveViolation`. Reports are charged
  to the sender. A policy-declared input bound raises the reserve but never lowers it. A scripted policy at r > 2 stays
  within its reserve, but usage above a declared bound still raises `ReserveViolation`. The live `LLMPolicy` keeps the
  runtime's bound, pinned exactly at every step. The invariants also hold at r = 3, where the declared bound binds.
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

- **Experiment 0b** (`tests/test_exp0b.py`):
  - the bootstrap does not depend on the order of the cells, and `evaluate` and `criteria_check` give identical output
    under different `PYTHONHASHSEED` values (amendment 0b-0); both tests fail on the unfixed code;
  - Experiment 0 keeps its paths, constants and frozen file (its sha256 is pinned);
  - the 0b constants differ from Experiment 0's in exactly the four monetary values;
  - 0b has its own spec, frozen file and results root, and its manifests record the experiment and SPEC_0B.md;
  - the committed 0b freeze verifies and is the pre-registered one;
  - `report` refuses a suite from another experiment, and a 0b suite reports as Experiment 0b.

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

Update (2026-09-30): the live pilot has since run outside this repository (see the log), and Experiment 0b has a
non-provisional freeze. No `developmental` or `router` LLM output exists, and no main run has been started.

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

| date | kind | sha256 of the frozen file | R | notes |
|---|---|---|---|---|
| (initial commit) | PROVISIONAL (no pilot) | a39cf404…9544f6 | 3 | gate passed with no repair steps; p = 0.9 and cv = 0.25 are defaults. Superseded |
| after code review | PROVISIONAL (no pilot) | 910bf202…dbb6f9 | 3 | the reserve disclosure lengthened the prompt; mechanical repair took 1 step (doc processing 0.100 → 0.105 s/token). `run` refuses this freeze |
| 2026-09-30 | **Experiment 0b**, from the live pilot | `data/exp0b/frozen.json` 0d10865d…ec50ff | 3 | gate (a)–(f) passed with repair steps (0, 0, 0); S/P/ambiguous 23/4/3; S_urgent 8, P_urgent 4, twin 8, D_urgent 3, I 0; IDEAL 0.855 at R = 3; prompt fingerprint 53790f89…f524b6. See SPEC_0B.md |

## Log

- Implementation and LLM-free verification complete. No pilot or main run yet: no API credentials were available.
- Adversarial code review completed; all 39 findings addressed, tests grown from 53 to 80, provisional freeze redone.
- 2026-09-29, live-run session: **blocked, no live call made.** This session was started to run the pilot, freeze
  and main run, but `ANTHROPIC_API_KEY` was **not set** in its environment (presence check only; the value was never
  read). Done offline: working tree clean at 32ac404; `anthropic` SDK 1.9.0 installed; `pytest -q` → 80 passed.
  Not done: the smoke call, pilot, non-provisional freeze, main run and report. No LLM output exists; nothing was
  fabricated; no constant, prompt, task or criterion changed. To unblock: add `ANTHROPIC_API_KEY` as an environment
  variable in the cloud environment's settings, then start a new session. Once the variable is present, the protocol
  resumes at Step 1.
- 2026-09-29, **pilot completed outside this repository** by the user, who reported these `pilot_stats`: 24 runs,
  80 LLM calls, r = 2.0052, 36 reasoning tokens, p90 output 203, `single` p95 elapsed 344.0196 s, `single` accuracy 1.0
  in every class, cost CV 0.008. The pilot logs (`results/pilot/`) are not in this repository.
  - **`freeze --pilot results/pilot` crashed** with `ReserveViolation: A0: realized step (in=12230, out=41) exceeds the
    reserve (in<=11435, out<=2048)`. This was an infrastructure/accounting bug in the calibration oracle at the grid
    point r = 2.5065. It is fixed as SPEC §11 item 16: a policy may declare its own input bound, and the larger bound
    is reserved. The live reserve is unchanged. An adversarial review (4 lenses, each finding re-verified) found no
    defect in the fix and three minor test/doc gaps, now closed: the live bound is pinned exactly, the oracle's
    declaration is pinned exactly, and a tight-balance reserve check was added. Tests grew from 80 to 100.
  - **The freeze then completes, but no candidate passes the gate.** Here it was rerun with the reported statistics
    injected in place of `pilot_stats`, because the logs are absent; every value that `freeze` reads is already rounded
    or clamped, so the result is the same. The output is `{"ok": false, "attempts": []}` with exit code 1.
    - **What fails, in all 343 mechanical-repair candidates** (cells listed for the unrepaired candidate):
      - gate (d): best fitness is below 0.5 in the urgent cells T01, T04, T07, T10, T09, T12 and T15, and `solo`
        fitness is below 0.3 in T04 and T10 urgent;
      - gate (f): `atstart8` starves children under the fixed allocation rule on T03 and T09, at the base point.
    - **What some candidates repair:** (b), T01, T04, T07 and T10 urgent being ambiguous rather than P, and (e), empty
      P_urgent and twin sets. 322 candidates fail only (d) and (f).
    - **Not caused by the fix:** the base-point oracle results are identical with and without it.
  - **No non-provisional freeze exists.** `data/frozen.json` is still the provisional 910bf202…dbb6f9, and the main run
    was not started. Under SPEC §8 validity (i), the gate must hold. No constant, prompt, task, criterion or scoring
    rule was changed to make it pass.
- 2026-09-30, **Experiment 0 recorded as: calibration failure after live pilot; no developmental-policy hypothesis
  test performed.** No valid Experiment 0 main run exists. `SPEC.md` and the provisional `data/frozen.json`
  (910bf202…dbb6f9) are unchanged.
- 2026-09-30, **Experiment 0b pre-registered** (`SPEC_0B.md`), implementing `EXPERIMENT_0B_PROPOSAL.md` (17da3c5):
  - **Reserve audit (step 0) passed**, run locally on the real pilot logs with `reserve_headroom.py`. Against the
    pre-declared rule:
    - planned = replayed = 24, `problems = {}`, `infrastructure_errors = {}`, `violations = 0`;
    - steps within 10% / 5% / 1% of the reserve: 0 / 0 / 0; minimum headroom 930 tokens (fraction 0.21405);
    - `first_step_allowance_used_fraction_max` = 0.07 (≤ 0.8);
    - worst later-step rate 0.52246256 tokens/char, which exhausts the allowance only at 44,518.5 characters
      (≥ 21,128); worst SQL-dominated rate 0.50909091;
    - largest later observation 13,245 characters; maximum output ÷ `max_tokens` 0.16309.

    The live reserve carries forward unchanged.
  - **Amendment 0b-0:** `contrast_ci` iterates the cells in sorted order, so bootstrap CIs, the criteria check's R and
    the §8 verdict no longer depend on `PYTHONHASHSEED`.
  - **Amendment 0b-1:** B = $1.392, V = $0.696, value of time $0.0000696/s (relaxed) and $0.0011136/s (urgent).
    Everything else is unchanged. Selected with `--experiment 0b`; Experiment 0 remains the default.
  - **Freeze**, offline and LLM-free, from the reported pilot statistics in `data/exp0b/pilot_stats.json`:
    `python -m devagents freeze --experiment 0b --pilot-stats data/exp0b/pilot_stats.json`.
    - Output: `{"ok": true, "R": 3, "steps": {"doc_per_token": 0, "urgent_vot": 0, "relaxed_vot": 0}}`.
    - Gate (a)–(f) passed; S/P/ambiguous 23/4/3; S_urgent 8, P_urgent 4, twin 8, D_urgent 3, I 0.
    - Criteria check at R = 3: IDEAL 0.855, WASTEFUL 0.005, every other policy 0.000.
    - It matches the proposal's expectations exactly; the calibration cells are identical to the proposal's C′. A
      repeat under `PYTHONHASHSEED=7` gave an identical file apart from `created_at`.
    - `data/exp0b/frozen.json` sha256: `0d10865d595c013c362661da088272d35555fd298a963a88993bec4cf9ec50ff`.
    - Prompt fingerprint: `53790f89f2a6ebef062d9ad31bd77d79546381fa2d4765302334ee9588f524b6`.
  - Tests grew from 100 to 109, all passing.
  - No live developmental or router output exists; no Anthropic API call was made. The main run has not been
    started. Next: `python -m devagents run --experiment 0b`.
- 2026-09-30, **Experiment 0b main run completed** (run locally by the experimenter; the logs in
  `results/exp0b/main` are not in this repository). Recorded here on 2026-10-01; this entry was missing and is
  appended, not back-dated.
  - **360/360 planned runs completed, 0 infrastructure failures**, R = 3, under the frozen configuration
    `data/exp0b/frozen.json`, sha256 `0d10865d595c013c362661da088272d35555fd298a963a88993bec4cf9ec50ff`.
  - **Report verdict: UNINFORMATIVE.** Validity condition (v), the realized manipulation check, **FAILED**:
    - B-urgent: `central` mean fitness 0.2830, `single` 0.3552 (required: `central` > `single`; failed);
    - B-relaxed: `central` 0.8244 < `single` 0.8771 (as required);
    - A: `single` 0.8913 ≥ `central` 0.8821 (as required).
  - The independent recomputation with `analysis/exp0b_diagnostic/traces.py` reproduced the report exactly, and the
    evaluator's criteria statistics agree with it.
  - **Descriptive findings (no verdict weight):**
    - `developmental` made zero SPAWN attempts in its 90 runs, and `router` zero in its 90 runs; no SPAWN was
      rejected. In the P cells both roots read every document in one QUERY.
    - `central` created exactly one child in every main run, and in every pilot run. No pilot or 0b run ever had two
      or more children.
    - Offline (LLM-free, real runtime modes, 0b constants, the live token statistics r 2.0277 and 45 reasoning
      tokens): a one-child `central` scores 0.279 against 0.343 for `single`, and the calibrated 3–4-child fan-out
      0.548. The failed check is explained by the realized one-child topology.
  - **These descriptive findings do not override or retrospectively change the verdict.** Experiment 0b is
    permanently recorded as **UNINFORMATIVE because the preregistered realized manipulation check failed.**
  - Diagnostic: `EXPERIMENT_0B_DIAGNOSTIC.md`, commit `44da120e65f3cb391e85a911e637d8a495ebf298`.
  - Decision memo: `EXPERIMENT_0C_DECISION.md`, commit `931a7c1e9138436aa960140611aab1b81c4cc9cc` (accepted: option
    B, a small clean replication with a scripted `central`).
- 2026-10-01, **Experiment 0c pre-registered** (`SPEC_0C.md`), implementing option B of
  `EXPERIMENT_0C_DECISION.md` (931a7c1): a held-out X2 instrument pilot (4 runs), then a narrow Stage 1 (36 runs), with
  a scripted `central` and the `developmental` treatment unchanged. Implementation and pre-registration only: **no API
  call was made, no live run was started, and Experiment 0b is unchanged** (still UNINFORMATIVE).
  - **Pre-registration file:** `data/exp0c/prereg.json`, sha256 (LF-normalized)
    `75e478ca485462ebedf759b63c4dfba94c2b6a4fc157c5aa90aa39618e6f78d0`. It pins the constants (0b's), the treatment
    hashes, the scripted topologies, both suites, the rules, the deciding code and the offline geometry.
  - **The only scientific change:** `central`'s first step is the oracle's pre-existing one-shot SPAWN, charged like a
    calibration oracle step (frozen r = 2.0052, 36 reasoning tokens) and logged as `SCRIPTED_ACTION`. Topologies:
    X2 urgent `fanout3` (the unchanged calibration rule at the 0b freeze's constants; pre-declared in the memo),
    T01/T07 urgent `fanout3`, T04/T10 urgent `fanout4` (the 0b freeze's `router_div`), partition `docs[i::k]`.
  - **Stage 0 offline checks (`python -m devagents exp0c verify`): all 15 pass.** They cover: 0/0b frozen files
    unchanged; the 0b freeze verifies; the 0b prompt fingerprint; `prereg.json` equals its recomputation; k and
    partitions; t0-only objectives; SPAWN serialization; suite sizes; mechanics (allocation, lifetime, fees, caps,
    reserves); geometry; the treatment files and the request/event stream equal 0b's own code (67c9d50); 0b's caps;
    the scripted step reproduces the oracle fan-out exactly. A simulated CRLF (Windows) checkout verifies identically.
  - **Offline geometry, Stage 1 means** (fitness; single / one-child central / scripted central): frozen assumptions
    0.3449 / 0.2822 / 0.5540; the 0b main run's token statistics (r 2.0277, 45 reasoning tokens) 0.3430 / 0.2787 /
    0.5490. X2: 0.3545 / 0.2914 / 0.5569 (frozen), 0.3526 / 0.2880 / 0.5524 (live).
  - **Infrastructure-only fixes:** UTF-8 report writes (the Windows cp1252 failure on U+2212) and a stdout that
    replaces unencodable characters; LF-normalized hashing in the 0b tests. No number changes.
  - **Review:** four independent reviewers and a verifier. Two blocking findings (a re-run could re-attempt spent runs
    and overwrite a decision; an interrupted run's partial live log would be deleted) and the important ones were fixed
    before this pre-registration was generated.
  - Tests grew from 109 to 202, all passing.
  - **Next live action:** `python -m devagents exp0c pilot` (the 4-run X2 pilot only). Stage 1 runs only after a PASS,
    and after `data/exp0c/pilot_record.json` and the pilot's outcome are committed here.
- 2026-10-01, **Experiment 0c completed: X2 pilot PASS, Stage 1 NO-GO (criterion 2 fired).** Run locally by the
  experimenter under the pre-registration `data/exp0c/prereg.json` (sha256, LF-normalized,
  `75e478ca485462ebedf759b63c4dfba94c2b6a4fc157c5aa90aa39618e6f78d0`). The raw result directories
  (`results/exp0c/pilot`, `results/exp0c/stage1`) are local and gitignored; they are preserved unmodified and are not
  in this repository. The numbers below are as reported from them.
  - **X2 instrument pilot:** 4/4 runs completed; **PASS**.
    - Mean fitness on X2 urgent: scripted `central` 0.5661, `single` 0.3667.
    - Scripted `central` created exactly 3 children and ran them in parallel. Quality stayed 1, elapsed time fell from
      about 344 s to about 133 s, and money rose, but total fitness was clearly higher.
    - Pilot record: `data/exp0c/pilot_record.json`, committed in 1797759 (manifest `created_at` 2026-10-01T14:42:30Z;
      `pilot_decision.json` sha256 `f224ee15cf1eec7dbe1d44b495739a25ff5e966c76165c01ee1b087e37927be2`).
    - Documentation deviation: SPEC_0C.md §6 asked for this EXPERIMENT_STATUS.md entry before Stage 1. Only the
      pilot record was committed then, which is what the code gate requires and checks. The entry is appended here,
      after the fact; no data, rule or decision is affected.
  - **Stage 1:** 36/36 runs completed (T01, T04, T07, T10 urgent × `single`, scripted `central`, unchanged
    `developmental` × R = 3).
    - Every gate passed, in order: completion, treatment identity, `single` validity, scripted-`central` integrity, and
      the live manipulation (mean fitness: scripted `central` 0.5583 > `single` 0.3552).
    - Scripted `central` was parallel in 12/12 runs.
    - **`developmental` was parallel in 0/12 runs and spawned in 0/12.** parallel_rate(P) = 0.00 < 0.50, so
      **criterion 2 fired**. **Result: NO-GO.**
    - The report states: "Under a live-validated B-urgent manipulation, the unchanged developmental treatment triggers
      the preregistered never-spawn criterion. Under the full SPEC §8 design this criterion alone would make H NOT
      SUPPORTED in a valid full experiment, but this narrow Stage 1 does not itself constitute a full §8 verdict."
    - This is **not a full SPEC §8 verdict**. **No Stage 2 was run.**
    - **Behavioural observation,** reported separately as pre-registered: a small number of scripted-`central`
      children did not read every assigned document. The runs stayed mechanically intact, and this counts as child
      behaviour, not as an infrastructure or implementation failure.
  - **Consistency with the offline prediction** (pre-registered geometry at the 0b main run's token statistics):
    - X2: `single` 0.3526 and scripted `central` 0.5524 predicted, against 0.3667 and 0.5661 observed;
    - Stage 1: `single` 0.3430 and scripted `central` 0.5490 predicted, against 0.3552 and 0.5583 observed.

    Stage 1 `single` (0.3552) equals Experiment 0b's B-urgent `single` mean.
  - Not yet recorded here: the sha256 of `results/exp0c/stage1/stage1_decision.json`, which is local.
- 2026-10-02, **Gate 0 (offline scientific feasibility): FAIL.** Implemented after postmortem §8
  (EXPERIMENT_0C_POSTMORTEM_AND_NEXT_DECISION.md, f848ab4), with the deviations declared in GATE_0_SPEC.md §6, offline
  and LLM-free. **Zero API calls.** No 0b/0c
  specification, policy, prompt or result changed. Spec `GATE_0_SPEC.md`, report `GATE_0_REPORT.md`.
  - **Frozen before any candidate evaluation.**
    - acceptance.json v3 (sha256 `80cbe516a5cb3e7bdbd51702764be0d33c273631504978293013f3f1ac391885`), spec and
      round-1 candidates.
    - Pinned by the audit's genesis entry (`data/gate0/audit.jsonl`, genesis hash `ec505a1a…`, commit 29a7dfd,
      pinning 31718d2), after two adversarial reviews and a final pre-genesis check.
  - **Round 1, evaluation 1** (the only evaluation; its start was published before it ran, beb48d6):
    - **Mechanical decision FAIL** (c2f01fd).
    - G1 integrity, G2 sanity and G7 dead-branch release pass.
    - G3/G4 fail: no qualifying cell. G5 fails narrowly. G8 fails vacuously. G9 was not computed.
    - Round 1 was closed as FAIL in the audit (b8702af). **No round 2 is registered** (report §7).
  - **Readings** (report §4–§5; descriptive post-hoc analysis from the logged records,
    `analysis/gate0/posthoc_round1.json`):
    - **Adaptive value over the best t0 router is real but small:** 0.032–0.056 at the base point in the six urgent
      cells, 0 in relaxed cells, and ≥ δ = 0.03 at every grid point only in A1 and A2 urgent.
    - **A one-line rule per template reproduces the adaptive oracle** in every urgent cell at every grid point (within
      0.0065 in A; exactly in B: the unconditional pipeline `W:spec2+dissolve` at 17 of 18 grid points, and a t0 one-line rule at
      g17). The one-line generic
      workflow captures one template at every grid point. No advantage over a simple deterministic controller is
      claimed.
    - **The follow-up cannot be powered.** Treating all six urgent cells as qualified: deliberation power 0.000 (high-effort
      checkpoints cost about 0.147 fitness each, 2–6 per run); presentation power 0.009 against the frozen baseline and
      0.115 against the router alone.
    - **Adversarial validation:** 41 agents found no implementation defect that changes a criterion. They re-derived
      every gated value from `records.json` independently.
  - **Consequence:** under postmortem §10 rule 2, Gate 0 failed, so **the program stops, with zero API calls.**
    - Stage A is not authorized.
    - The tripwire (rule 6) is unaffected.
  - **Still not recorded:** the sha256 of `results/exp0c/stage1/stage1_decision.json`, which is local. Command, run
    in the experimenter's checkout:
    `py -c "from devagents.evals.exp0c import sha256_lf; print(sha256_lf('results/exp0c/stage1/stage1_decision.json'))"`
