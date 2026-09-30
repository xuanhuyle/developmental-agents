# SPEC 0b — Experiment 0b: resource-aware division at the pilot-measured price level

**Status: pre-registration**, amending [`SPEC.md`](SPEC.md). It was written and committed before any live
`developmental` or `router` LLM output existed.

- **SPEC.md applies in full**, except where amendments 0b-0 to 0b-5 below change it. §7 (the calibration gate and the
  criteria check), §8 (falsification) and §9 (estimands) must not be weakened after any Experiment 0b main-suite LLM
  result exists.
- **The freeze** is a git commit of `data/exp0b/frozen.json`, made before the first Experiment 0b main run. Its
  sha256 and prompt fingerprint are recorded in `EXPERIMENT_STATUS.md`.
- **The design and its derivation** are in [`EXPERIMENT_0B_PROPOSAL.md`](EXPERIMENT_0B_PROPOSAL.md) (commit 17da3c5),
  which was accepted as the design. This document is the binding pre-registration; the proposal is its rationale.

## 1. Record of Experiment 0

Experiment 0 is recorded as: **calibration failure after live pilot; no developmental-policy hypothesis test
performed.**

- The live pilot completed: `single` and `central` only, 24/24 runs on the held-out tasks X1–X3.
- After an accounting fix to the calibration oracle (520947a, b76cbcd), the post-pilot freeze completed, but none of
  the 343 pre-registered mechanical-repair candidates passed the gate. Gate (d) (economic viability) and gate (f)
  (feasibility) failed in all 343.
- No valid Experiment 0 main run exists. No `developmental` or `router` run took place. Experiment 0 is not a result
  for or against H.
- Experiment 0's files are unchanged and remain reproducible: `SPEC.md`, the provisional `data/frozen.json`, and its
  `EXPERIMENT_STATUS.md` entries. The command line still uses Experiment 0 unless `--experiment 0b` is given.

## 2. Question and hypotheses

Unchanged: SPEC.md §1 and §2. Can the same resource-aware lifecycle policy remain effectively unicellular where
division is uneconomic, and divide where division improves the time–money–quality frontier?

## 3. Pilot (reused, not re-run)

Experiment 0b reuses the Experiment 0 live pilot, which ran `single` and `central` only. Its `pilot_stats` output was:

| statistic | value |
|---|---|
| runs / LLM calls | 24 / 80 |
| input_scale r | 2.0052 |
| median reasoning tokens | 36 |
| p90 output tokens | 203 |
| `single` p95 elapsed | 344.0196 s |
| `single` accuracy (solo / parallel / cross) | 1.0 / 1.0 / 1.0 |
| cost CV | 0.008 |

**Where the freeze gets these numbers.** The pilot logs (`results/pilot/`) are not in the repository. The freeze
therefore reads the reported statistics from `data/exp0b/pilot_stats.json` (0b-3). This is exact, because every value
`freeze` uses is already rounded or clamped:
- r and the reasoning tokens are `pilot_stats`'s rounded outputs;
- `min_step_tokens` = max(256, 203) = 256;
- the deadline is max(1500, 2 × 344.0196) = 1500 s;
- the cost CV used is max(0.25, 0.008) = 0.25;
- accuracy is 1.0 in every class.

## 4. Step 0: reserve-headroom audit — PASSED

The live step reserve was audited on the real pilot logs before this pre-registration. The run was local, with:

```
py analysis\exp0b\reserve_headroom.py results\pilot --json results\exp0b_analysis\reserve_headroom.json
```

The script replays every logged pilot run through the unchanged runtime, feeding it the logged actions and API usage,
and recomputes the reserve of every live step. The decision rule was declared in EXPERIMENT_0B_PROPOSAL.md §2 before
the audit ran.

| rule | threshold | audit result | verdict |
|---|---|---|---|
| 1. every planned run replays exactly | planned = replayed, no problems | 24 = 24, `problems = {}` | pass |
| 2. no reserve violation | 0, none in errors.jsonl | `violations = 0`, `infrastructure_errors = {}` | pass |
| 3. no step within 5% of its reserve | 0 steps | steps within 10% / 5% / 1%: 0 / 0 / 0 | pass |
| 4. first-step allowance use | ≤ 0.8 | `first_step_allowance_used_fraction_max = 0.07` | pass |
| 5. size that exhausts the allowance at the worst later-step rate | ≥ 21,128 characters | 44,518.5 (worst rate 0.52246256 tokens/char) | pass |
| 5′. the same for SQL-dominated steps | ≥ 21,128 characters | worst rate 0.50909091 → 110,000 characters | pass |

Other audit numbers:
- minimum input headroom: 930 tokens (minimum headroom fraction 0.21405);
- largest later-step observation: 13,245 characters;
- maximum output ÷ `max_tokens`: 0.16309.

**Consequence.** The live reserve carries forward **unchanged**:
- `REQUEST_OVERHEAD_TOKENS` = 1000;
- the input bound of 1 token per 2 new characters;
- the output reserve logic.

The residual risk stated in the proposal remains: pathological observations (duplicate targets, very wide SQL, many
simultaneous reports) are not covered. A `ReserveViolation` there is an infrastructure error under SPEC.md §8.

## 5. Amendments

### 0b-0. Reproducible bootstrap (infrastructure)

- **The defect.** `contrast_ci` in `devagents/evals/analysis.py` built its per-task lists by iterating a `set` of cell
  keys before drawing from its seeded random generator. Bootstrap CIs, and therefore the criteria check's R and the
  §8 verdict's CIs, depended on `PYTHONHASHSEED`.
- **The fix.** It now iterates `sorted(cells)`. No rule changes; the same bootstrap is now reproducible.
- **The tests** (`tests/test_exp0b.py`):
  - the CI is identical whatever order the cells are given in;
  - `evaluate` and `criteria_check` give byte-identical output under different `PYTHONHASHSEED` values.

### 0b-1. Constants

These four monetary constants change. Nothing else changes.

| constant | Experiment 0 | **Experiment 0b** |
|---|---|---|
| run budget B (both regimes) | $1.00 | **$1.392** |
| task value V (both regimes) | $0.50 | **$0.696** |
| value of time, `relaxed` | $0.00005 / s | **$0.0000696 / s** |
| value of time, `urgent` | $0.0008 / s | **$0.0011136 / s** |

**Derivation (fixed before this pre-registration).** s = 1.392 is the median over the 256 base-point oracle
organizations of money(r = 2.0052, 36 reasoning tokens) ÷ money(r = 1, 150 reasoning tokens), at Experiment 0's
constants: 1.392499, rounded to three decimals. Each constant is its Experiment 0 value × s.

**What 0b-1 supersedes, for Experiment 0b only:**
- SPEC.md §3.4's "V = $0.50";
- §4's regime values and $1.00 budget;
- the header rule that constants change only through the §7.4 mechanical procedure. 0b-1 is a one-time, documented
  change made before the freeze.

**Implementation.** `devagents.config.exp0b_constants()`, selected with `--experiment 0b`.

### 0b-2. Reserve audit before the freeze

Done; it passed (§4). No reserve or runtime change was made.

### 0b-3. Freeze

```
python -m devagents freeze --experiment 0b --pilot-stats data/exp0b/pilot_stats.json
```

- It runs the unchanged SPEC.md §7.4 procedure from the 0b-1 constants: perturbation grid, gate, mechanical repair,
  criteria check.
- It writes `data/exp0b/frozen.json`, which records `"experiment": "0b"`, the pilot statistics and their source, and
  the sha256 of this document and of SPEC.md.

**Expected outcome**, from the proposal:
- gates (a)–(f) pass with repair steps (0, 0, 0);
- S 23, P 4, ambiguous 3;
- S_urgent 8, P_urgent 4, twin 8, D_urgent 3, I 0;
- R = 3.

These are expectations, not targets. Any other outcome is reported as it is and is not tuned. The actual outcome is
recorded in `EXPERIMENT_STATUS.md`.

**Optional local cross-check from the pilot logs.** This writes a separate file:

```
python -m devagents freeze --experiment 0b --pilot results/pilot --out results/exp0b/freeze-from-logs.json
```

It must give the same constants, assumptions, calibration, R and prompt fingerprint. Only `created_at`, `pilot` and
`pilot_source` may differ.

### 0b-4. Artefacts and commands

- **Artefacts.** Experiment 0b uses `SPEC_0B.md`, `data/exp0b/frozen.json` and `results/exp0b/` (`main/`, `smoke/`,
  `exploratory/`). Experiment 0's files are never read or written by an Experiment 0b command.
- **Freeze:** `python -m devagents freeze --experiment 0b …`, as in 0b-3.
- **Main run:** `python -m devagents run --experiment 0b`.
  - It refuses to start unless `data/exp0b/frozen.json` exists, is the Experiment 0b freeze, is not provisional, and
    verifies. Verifying means the recomputed calibration, sets and prompt fingerprint are identical.
  - It writes to `results/exp0b/main` with R repeats from the freeze.
- **Report:** `python -m devagents report results/exp0b/main --experiment 0b`. It refuses a suite whose manifest names
  another experiment.
- **Validity condition (i)** (SPEC.md §8) reads, for Experiment 0b: "The §7 gate holds, and `data/exp0b/frozen.json`
  matches."

### 0b-5. Record

`EXPERIMENT_STATUS.md` records:
- Experiment 0 as in §1;
- the reserve audit as in §4;
- this pre-registration and its commit;
- the 0b freeze's outcome, its sha256 and its prompt fingerprint.

## 6. Carried forward unchanged

Everything not amended above is carried forward from SPEC.md exactly. That includes:

- **Question and hypotheses:** H and H2, and what a SUPPORTED, NOT SUPPORTED or UNINFORMATIVE verdict means (§1, §2).
- **Resource model:**
  - the normative cost and time table: prices, fees and latencies;
  - event semantics;
  - money conservation;
  - the step reserve, including `REQUEST_OVERHEAD_TOKENS` = 1000 and the policy-declared bound;
  - every invariant (§3.1–§3.3).
- **Fitness:** the fitness formula, with V as amended; `w_coord` = 0; failure penalty 1.0 (§3.4).
- **Tasks and run plan:**
  - task questions, answers, classes, subtypes and routes: 15 main tasks and 3 pilot tasks;
  - the synthetic world;
  - the two regimes, which differ only in value of time;
  - the shared 1500 s deadline;
  - the plan: every (task, regime, repeat) block runs all four modes in a seeded order (§4).
- **Lifecycle actions:** WORK, QUERY, SPAWN, MESSAGE, WAIT and TERMINATE, with their rules (§5).
- **Modes and prompts:**
  - `single`, `central`, `router` and `developmental`;
  - the fixed allocation share 0.5 and lifetime share 0.6;
  - K = 8 (max concurrency 9);
  - caps: 20 steps per agent, 16 agents per run, 10 requests per QUERY;
  - prompt templates and MODE RULES (§6).

  The prompts' rendered numbers change with 0b-1, so the prompt fingerprint is re-frozen.
- **Calibration:**
  - oracle organizations;
  - the perturbation grid, r × {0.75, 1, 1.25}, reasoning × {0.5, 1, 2}, extra WORK steps {0, 1};
  - δ = 0.03;
  - S, P, ambiguous and I labels;
  - **gate (a)–(f) with the same thresholds**: every A cell S; every B-urgent cell P and every B-relaxed cell S;
    every shortcut cell S; at the base point best fitness ≥ 0.5 and `solo` ≥ 0.3 in every cell; S_urgent, P_urgent,
    twin and D_urgent non-empty; clean oracle runs (§7.1–§7.2).
- **Criteria check and freeze:** synthetic policies, the rule for choosing R (smallest R in {3, 5, 8, 10} with IDEAL
  supported ≥ 80% and every other policy not supported ≥ 95%), and the mechanical-repair procedure (§7.3–§7.4).
- **Falsification criteria 1–5, unchanged** (§8):
  1. always-spawn collapse;
  2. never-spawn collapse;
  3. no differentiation: within a regime, twin, and dissociation, each against 0.30;
  4. no frontier gain over `single`: 4a cost gain on P, 4b quality loss, 4c cost loss outside P;
  5. `central` suffices on S.

  The estimands and the two-level bootstrap are unchanged: 10,000 resamples, seed 0, with cells now iterated in
  sorted order (0b-0).
- **Validity and errors:** validity conditions (i)–(vi), with (i) as in 0b-4. The infrastructure-error list and its 3
  retries (§8).
- **Metrics, event log and limitations:** metrics and the event log (§9); what the experiment cannot show (§10).
- **Model:** `claude-opus-5-5` at effort `low`, with structured output. No other model or provider.
- **Pilot measurements:** reused (§3), including `min_step_tokens` = 256.

## 7. Limitations specific to Experiment 0b

Inherited from Experiment 0's design, and not repaired:
- only 4 designed P cells, all parallel-urgent;
- no I cells, so H2 cannot be positive;
- thin S margins;
- a budget that does not bind the best organizations;
- child allocation that matters only as a floor;
- lifetimes that do not bind.

Specific to 0b:
- 0b quantities are in list-price dollars, 1.392× Experiment 0's design units.
- The pilot's accuracy of 1.0 makes the criteria check's power estimate optimistic.
- The reserve does not cover pathological observations (§4).

See EXPERIMENT_0B_PROPOSAL.md §11.
