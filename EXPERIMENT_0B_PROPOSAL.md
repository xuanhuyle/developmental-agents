# Experiment 0b: proposal

**Status: proposal only. Nothing here is implemented or pre-registered.**

- **Starting point:** commit b76cbcd on main.
- **Experiment 0:** remains in git history as it is. Its status is: *calibration failure after the live pilot; no
  developmental-policy hypothesis test was performed.*
- **Live data:** every number here comes from LLM-free simulation driven by the live pilot's reported statistics. No
  live developmental or router output exists, and none was used (§12).

The scientific question is unchanged:

> Can the same resource-aware lifecycle policy remain effectively unicellular where division is uneconomic, and divide
> where division improves the time–money–quality frontier?

**Recommendation in one line:** multiply the environment's dollar-denominated values (run budget B, task value V and
both regimes' value of time) by **s = 1.392**.
- s is derived by a fixed rule from the pilot's two measured token statistics.
- It is the median factor by which those statistics raised the money cost of the calibration oracle's organizations.
- Nothing else changes: tasks, prompt templates, K, the allocation rule, the gates, δ and the criteria stay as they are.
- With it, the unchanged pre-registered freeze passes the gate with **no repair**, reproduces Experiment 0's designed
  S/P/ambiguous structure on **30/30** cells, and gives **R = 3**.

**One new concrete infrastructure defect** was found during this work (§1, amendment 0b-0). The pre-registered
evaluator's bootstrap iterates a Python `set`, so its CIs, and hence the criteria check's R, depend on `PYTHONHASHSEED`.
It is not fixed here, because this task commits only the proposal and scripts. Its one-line fix must precede the 0b
freeze.

## Reproducing this document

The scripts read the repository and write only under `results/`, which is gitignored:

```bash
python analysis/exp0b/study.py                                       # ~25 min on 4 cores -> results/exp0b_analysis/*.json
python analysis/exp0b/tables.py > results/exp0b_analysis/tables.md   # every table below
python analysis/exp0b/reserve_headroom.py results/pilot              # §2; needs the pilot logs
```

`study.py` modifies no repository file. Candidate constants exist only in memory. Each candidate runs the **unchanged**
freeze procedure (`experiment.freeze`: perturbation grid, gate, mechanical repair, criteria check; SPEC §7).

**Two things are emulated in memory:**
- **The fixed allocation share** is passed to the oracle's run configuration.
- **The bootstrap's cells are iterated in sorted order**, the proposed fix 0b-0. Labels, margins and fitness are
  deterministic anyway. With sorted order the criteria-check rates are too: C′'s IDEAL rate is 0.855 under every
  `PYTHONHASHSEED` tried. With the current evaluator it varies, for example 0.825–0.865 for C′, and R can flip between
  3 and 5 for a borderline candidate (×1.3).

**The pilot logs are not in the repository**, so `study.py` injects the statistics you reported. That is exact for the
freeze, because every value it reads is rounded or clamped:
- r = 2.0052 and 36 reasoning tokens are `pilot_stats`'s rounded outputs;
- `min_step_tokens` = max(256, 203) = 256;
- the deadline is max(1500, 2 × 344.0196) = 1500 s;
- the cost CV is max(0.25, 0.008) = 0.25;
- accuracy is 1.0 in every class.

---

## 1. Experiment 0 post-mortem

**What happened**
- **Pilot:** `single` and `central` completed 24/24 runs on X1–X3, with 80 LLM calls. Measured values: r = 2.0052,
  median reasoning 36 tokens, p90 output 203, `single` p95 elapsed 344.0196 s, `single` accuracy 1.0 in every class.
- **First freeze:** it crashed with a `ReserveViolation` in the LLM-free oracle at the grid point r = 1.25 × 2.0052.
  That was an accounting bug, fixed and reviewed in 520947a and b76cbcd. All 8,752 oracle runs that already completed
  kept identical simulated metrics.
- **Freeze after the fix:** it completes, but **none of the 343 pre-registered mechanical-repair candidates passes the
  gate**. It prints `{"ok": false, "attempts": []}` and exits with code 1.
- **Result:** validity condition (i) (SPEC §8) requires the gate to hold, so no valid main run exists. No developmental
  or router run took place.

**Two independent blockers persist in all 343 candidates:**
- **Gate (d), economic viability.** In each of seven urgent cells (T01, T04, T07, T09, T10, T12 and T15), the best
  organization's fitness is below 0.5. In T04 and T10 urgent, `solo` fitness is also below 0.3.
- **Gate (f), feasibility.** `atstart8` starves children under the fixed allocation rule on T03 and T09.

**Why.** The environment was calibrated before the pilot at r = 1 and 150 reasoning tokens. The pilot measured
r = 2.0052 and 36.
- Over all 256 base-point oracle organizations, the pilot's accounting multiplies money cost by a median **1.392**
  (1.016–1.461). Input tokens doubled, but output fell with the reasoning tokens, and query fees did not change.
- It multiplies simulated elapsed time by a median 0.925.
- Mechanical repair can move only document latency and the value of time. It has no lever on money scale, so it cannot
  restore (d).

**The design was near the thresholds even before the pilot.** In the frozen pre-pilot design (the provisional
`data/frozen.json`: r = 1, document latency repaired to 0.105 s/token):
- the (d) cells' best-division fitness was 0.527–0.551, only 0.03–0.05 above 0.5;
- `solo` fitness in T04 and T10 urgent was **0.305, only 0.005 above the 0.3 floor**.

Gate (f) is a knife-edge: it fails by 0.1–0.5% of a child's need.

**A new infrastructure defect, found in this work.** `devagents/evals/analysis.py` `contrast_ci` builds its per-task
lists by iterating a `set` of cell keys, before drawing from a seeded random generator. The bootstrap CIs therefore
depend on `PYTHONHASHSEED`, and so do:
- the criteria check's supported rates and R (at every freeze);
- the §8 verdict's confidence intervals (in `report`).

Point estimates are unaffected. The provisional freeze's R (3) and C′'s R (3) happen to be stable, but a borderline
candidate's R changes with the seed. The fix is amendment 0b-0.

**How the record should read.** *Experiment 0: calibration failure after live pilot; no developmental-policy
hypothesis test performed.* It is not a negative result for H.

## 2. Reserve-headroom audit (step 0)

**The audit could not be run here.** The pilot logs are not in this environment. The median cannot settle reserve
safety, and this section explains why before giving the command.

**What the reserve assumes.** The live step reserve's input bound is:
- the previous step's exact usage;
- plus 1 token per 2 new characters, twice the 4-characters-per-token estimator;
- plus a fixed 1,000-token request allowance.

**Why the median is not enough.**
- The pilot's median r = 2.0052 is total API input divided by the estimator count of the visible text. The numerator
  includes the injected schema and request framing.
- So at the median, new text costs at most about what the bound assumes, and nearly all of the slack is the 1,000-token
  allowance.
- Whether that suffices depends on the **tail** of the per-character rate on later steps, multiplied by the observation
  size.

**Observation sizes**, computed by `study.py observation_sizes()`:
- The oracle's largest single new observation is 13,413 characters in the main tasks and 13,245 in the pilot tasks.
- One QUERY of the ten largest distinct documents, followed by a status block listing 8 children, is **21,128
  characters**. There the allowance covers a rate of at most 0.5 + 1000/21,128 ≈ 0.547 tokens per character.
- Observation size is **not bounded** in principle. Duplicate targets, wide SQL results (up to 50 rows of any width)
  and several child reports delivered at once can produce observations over 50,000 characters. At that size the
  allowance covers only about 0.52 tokens per character, and number-dense SQL may tokenize more densely than prose.

**The exact local command.** Run it where `results/pilot` exists, on a checkout whose `devagents/agents/prompts.py`
equals the pilot's (unchanged from 32ac404 to b76cbcd). On Windows use `py` and backslashes:

```bash
python analysis/exp0b/reserve_headroom.py results/pilot --json results/exp0b_analysis/reserve_headroom.json
```

**How it works.**
- The log does not record the reserve, so the script **replays** every logged pilot run through the unchanged runtime.
  The replay policy returns the logged actions and the logged API usage.
- The runtime then recomputes every observation, status block and `_input_upper_bound` exactly.
- A run counts only if its replayed log equals the original, ignoring wall-clock fields and the policy's name.
- Planned runs without a complete log are listed as problems, and the exit code is 1.
- It prints the checkout's identity (git HEAD, and sha256 prefixes of `prompts.py` and `runtime.py`).
- It prints numbers only: no prompt, document text, answer, message content or key.
- Validation:
  - my test: a synthetic 24-run pilot from the test suite's fake Anthropic client replayed 24/24 exactly, including a
    refusal;
  - an independent reviewer: six synthetic pilots covering empty-content refusals, invalid JSON, plain and
    budget-capped truncation, central fixed-rule spawns, messages, waits, expiries, `budget_exhausted` and `max_steps`
    all replayed exactly;
  - a deleted log is reported, with exit code 1.

**What it reports.**
- in_tokens ÷ est_in_tokens: median, p90, p95, p99, max.
- Headroom (`_input_upper_bound` − in_tokens): absolute and relative quantiles, and the tightest step (run, agent,
  step).
- Steps within 10%, 5% and 1% of the reserve, and violations.
- The share of the 1,000-token allowance used, separately for first steps.
- New input tokens per new character on later steps: overall, for observations ≥ 2,000 characters, and for
  SQL-dominated versus document-dominated observations.
- The largest later-step observation seen.
- The observation size that would exhaust the allowance at the worst later-step rate ("Infinity" means never).
- The output-side ratio against `max_tokens`.
- `errors.jsonl` counts, by exception type only.
- With `--json`, one numeric row per live step (run, agent, step, in, in_upper, headroom, est_in, new_chars,
  max_tokens, first step, SQL share).

**Proposed decision rule, to be pre-registered in 0b.** The live reserve carries forward unchanged only if all of these
hold:
1. `planned_runs = replayed_runs`, `problems` is empty, and the exit code is 0.
2. `violations = 0`, and there is no `ReserveViolation` in `errors.jsonl`.
3. No step is within 5% of its reserve.
4. `first_step_allowance_used_fraction_max` ≤ 0.8.
5. `chars_that_exhaust_allowance_at_worst_later_rate` ≥ 21,128, and the SQL-dominated worst rate satisfies the same
   test.

**What the rule covers, and what it doesn't.**
- It protects realistic observations: the ten largest documents at once.
- It does not protect pathological ones (duplicate targets, very wide SQL, many simultaneous reports). A
  `ReserveViolation` there is an infrastructure error. It is retried up to 3 times and counts against completion,
  validity (iv). This residual risk is listed in §11.

**If the rule fails:** a **separate, documented infrastructure decision** is made before the 0b freeze. It is not part
of this economic redesign.
- The only levers are `REQUEST_OVERHEAD_TOKENS` and the per-character bound. Both are disclosed in the prompt, so
  changing either changes the prompt and the calibration.
- `study.py` must then be rerun to confirm the recommendation still passes.

## 3. Quantitative decomposition of the calibration failure

**Calibration used.** The unrepaired post-pilot calibration: Experiment 0's code-default constants (document latency
0.100), the pilot's base (r = 2.0052, 36 reasoning tokens), and the 18-point grid.
- Fitness = quality − money/V − VoT·elapsed/V.
- Elapsed time is split along the run's **critical path**, so its parts sum exactly to the elapsed time.
- "Pre-pilot design" means the provisional freeze.
- "Δ from the pilot (same constants)" is the same organization under r = 1 and 150 reasoning tokens, at the same
  constants. It isolates exactly what the pilot's measurements changed.

**Failing cells at the unrepaired post-pilot calibration (r = 2.0052, 36 reasoning tokens)**

Money and time are the two cost terms of the fitness, as fractions of V: fitness = quality − money/V − VoT·elapsed/V. Time is the critical path, so it sums to the elapsed time.

| cell | class/subtype | label (pre-pilot design) | gate violated | best solo | solo fit | best division | div fit | div money/V | div time/V | div agents | div LLM calls | solo money/V | solo time/V |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T01|urgent | parallel/- | ambiguous (P) | b, d best<0.5 | solo@r0 | 0.317 | fanout3@r0 | 0.470 | 0.320 | 0.210 | 4 | 8 | 0.133 | 0.549 |
| T03|relaxed | cross/dependent | S (S) | f | solo@r0 | 0.895 | fanout1@r0 | 0.831 | 0.163 | 0.006 | 2 | 5 | 0.099 | 0.005 |
| T03|urgent | cross/dependent | S (S) | f | solo@r0 | 0.815 | fanout1@r0 | 0.736 | 0.163 | 0.101 | 2 | 5 | 0.099 | 0.086 |
| T04|urgent | parallel/- | ambiguous (P) | b, d best<0.5, d solo<0.3 | solo@r0 | 0.295 | fanout4@r0 | 0.438 | 0.392 | 0.170 | 5 | 10 | 0.143 | 0.562 |
| T07|urgent | parallel/- | ambiguous (P) | b, d best<0.5 | solo@r0 | 0.317 | fanout3@r0 | 0.471 | 0.319 | 0.210 | 4 | 8 | 0.133 | 0.549 |
| T09|relaxed | cross/dependent | S (S) | f | solo@r0 | 0.817 | fanout1@r0 | 0.750 | 0.222 | 0.028 | 2 | 5 | 0.156 | 0.027 |
| T09|urgent | cross/dependent | ambiguous (ambiguous) | d best<0.5, f | solo@r0 | 0.411 | fanout3@r0 | 0.475 | 0.348 | 0.177 | 4 | 9 | 0.156 | 0.433 |
| T10|urgent | parallel/- | ambiguous (P) | b, d best<0.5, d solo<0.3 | solo@r0 | 0.295 | fanout4@r0 | 0.441 | 0.390 | 0.169 | 5 | 10 | 0.143 | 0.562 |
| T12|urgent | cross/dependent | ambiguous (ambiguous) | d best<0.5 | solo@r0 | 0.382 | fanout3@r1 | 0.466 | 0.323 | 0.211 | 4 | 8 | 0.152 | 0.466 |
| T15|urgent | cross/dependent | ambiguous (ambiguous) | d best<0.5 | solo@r0 | 0.412 | fanout3@r0 | 0.478 | 0.345 | 0.177 | 4 | 9 | 0.155 | 0.433 |

### 3A. Gate (d): economic scale

**Gate (d): where 1 − fitness comes from (fractions of V; urgent cells)**

| cell | org | fitness (pre-pilot design) | LLM money | query fees | coordination fees | LLM latency × VoT | doc latency × VoT | other time × VoT | Δ fitness from the pilot (same constants) | of which LLM money |
|---|---|---|---|---|---|---|---|---|---|---|
| T01|urgent | solo@r0 | 0.317 (0.327) | 0.109 | 0.024 | 0.000 | 0.012 | 0.538 | 0.000 | -0.035 | -0.042 |
| T01|urgent | fanout3@r0 | 0.470 (0.539) | 0.288 | 0.024 | 0.008 | 0.027 | 0.181 | 0.002 | -0.078 | -0.092 |
| T04|urgent | solo@r0 | 0.295 (0.305) | 0.111 | 0.032 | 0.000 | 0.012 | 0.549 | 0.000 | -0.036 | -0.043 |
| T04|urgent | fanout4@r0 | 0.438 (0.527) | 0.349 | 0.032 | 0.011 | 0.029 | 0.139 | 0.002 | -0.095 | -0.109 |
| T07|urgent | solo@r0 | 0.317 (0.327) | 0.109 | 0.024 | 0.000 | 0.012 | 0.538 | 0.000 | -0.035 | -0.042 |
| T07|urgent | fanout3@r0 | 0.471 (0.540) | 0.287 | 0.024 | 0.008 | 0.026 | 0.181 | 0.002 | -0.078 | -0.092 |
| T09|urgent | solo@r0 | 0.411 (0.427) | 0.131 | 0.025 | 0.000 | 0.018 | 0.414 | 0.002 | -0.036 | -0.046 |
| T09|urgent | fanout3@r0 | 0.475 (0.549) | 0.314 | 0.025 | 0.008 | 0.034 | 0.139 | 0.004 | -0.080 | -0.097 |
| T10|urgent | solo@r0 | 0.295 (0.305) | 0.111 | 0.032 | 0.000 | 0.013 | 0.549 | 0.000 | -0.036 | -0.042 |
| T10|urgent | fanout4@r0 | 0.441 (0.529) | 0.347 | 0.032 | 0.011 | 0.028 | 0.139 | 0.002 | -0.094 | -0.108 |
| T12|urgent | solo@r0 | 0.382 (0.397) | 0.131 | 0.021 | 0.000 | 0.017 | 0.448 | 0.002 | -0.037 | -0.047 |
| T12|urgent | fanout3@r1 | 0.466 (0.536) | 0.291 | 0.024 | 0.008 | 0.027 | 0.181 | 0.002 | -0.079 | -0.093 |
| T15|urgent | solo@r0 | 0.412 (0.428) | 0.130 | 0.025 | 0.000 | 0.017 | 0.414 | 0.002 | -0.036 | -0.046 |
| T15|urgent | fanout3@r0 | 0.478 (0.551) | 0.312 | 0.025 | 0.008 | 0.033 | 0.140 | 0.004 | -0.079 | -0.097 |

**Best division (fanout3 or fanout4).** 1 − fitness is 0.522–0.562. It breaks down as:

| component | share of V | share of the total |
|---|---|---|
| LLM money | 0.287–0.349 | 54–62% |
| document latency × VoT | 0.139–0.181 | |
| LLM latency × VoT | 0.026–0.034 | |
| query fees | 0.024–0.032 | |
| coordination fees and latency | ≈ 0.01 | |

- **Effect of the pilot:** −0.078 to −0.095 fitness. LLM money alone accounts for −0.092 to −0.109; time improved
  slightly, because there are fewer output tokens.
- **Size of the miss:** best-division fitness is 0.438–0.478, which misses 0.5 by 0.022–0.062.

**Best solo.** 1 − fitness is 0.588–0.705, of which document latency × VoT is 0.414–0.549. That is by design: reading
6–8 slow documents alone is what makes urgent parallel cells costly for `solo`. The pilot lowered solo fitness by only
0.035–0.037, but the design's margin on the 0.3 floor was only 0.005, so T04 and T10 urgent went from 0.305 to 0.295.

**Contribution of each named factor to the (d) failure:**
- **LLM monetary cost:** the cause of the failure. It is the component the pilot moved (+0.09–0.11 of V for
  divisions, +0.04–0.05 for solo), and it is the largest single term for divisions.
- **Simulated LLM latency:** small (0.01–0.03 of V), and slightly lower after the pilot.
- **Document-processing latency:** the largest term for solo, but unchanged by the pilot. It sets the level, not the
  change.
- **Value-of-time penalty:** all time terms together. They are 0.17–0.21 of V for the best division and 0.43–0.56 for
  solo. They set the level of urgent fitness, but not the pilot's change.

### 3B. Gate (f): division feasibility

**Gate (f): the starved organizations under the fixed allocation rule**

| cell | org | children | parent balance before SPAWN | spawn fees | available (share × (balance − fees)) | allocation per child | minimum viable per child | of which actual spend | of which step reserve | shortfall | starved children |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T03|relaxed | atstart8@r0 | 8 | $0.9680 | $0.0096 | $0.4792 | $0.0599 | $0.0599 | $0.0518 | $0.0081 | $0.00005 (0.1%) | 1/8 |
| T03|urgent | atstart8@r0 | 8 | $0.9680 | $0.0096 | $0.4792 | $0.0599 | $0.0599 | $0.0518 | $0.0081 | $0.00005 (0.1%) | 1/8 |
| T09|relaxed | atstart8@r0 | 8 | $0.9671 | $0.0097 | $0.4787 | $0.0598 | $0.0601 | $0.0520 | $0.0081 | $0.00029 (0.5%) | 6/8 |
| T09|urgent | atstart8@r0 | 8 | $0.9671 | $0.0097 | $0.4787 | $0.0598 | $0.0601 | $0.0520 | $0.0081 | $0.00029 (0.5%) | 6/8 |

What single change would cover the need, everything else at Experiment 0 values:

| cell | B needed | share needed | children the rule can fund at share 0.5 | need without the step reserve / allocation |
|---|---|---|---|---|
| T03|relaxed | $1.0008 | 0.5004 | 7 | 86.5% |
| T03|urgent | $1.0008 | 0.5004 | 7 | 86.5% |
| T09|relaxed | $1.0046 | 0.5024 | 7 | 86.9% |
| T09|urgent | $1.0046 | 0.5024 | 7 | 86.9% |

**How `atstart8` starves.**
- The root takes one step (≈ $0.032). The fixed rule then gives each of 8 children 50% × (balance − spawn fees) / 8 ≈
  **$0.0598–$0.0599**.
- A child (SQL, then documents, then TERMINATE) needs **$0.0599–$0.0601**, found by exact bisection with the rule's own
  lifetime. That is its actual spend, $0.0518–$0.0520, plus **$0.0081 of step reserve**. The reserve is the excess of
  the balance a child must hold before its final step (input bound × 4 µ$ + one message fee + 256 minimum output tokens
  × 22 µ$) over what that step costs.
- The shortfall is **$0.00005–$0.00029 (0.1–0.5%)**. On T03, one child in eight starves; on T09, larger
  qualifying-document reads starve six of eight.

**Contribution of each named factor:**
- **Insufficient total budget:** B ≥ $1.0008–$1.0046 alone would be enough.
- **The 50% share rule:** a share ≥ 0.5004–0.5024 alone would be enough.
- **Eight-way fan-out:** the rule funds 7 children, so K ≤ 7 alone would be enough, because it removes `atstart8`.
- **The per-child step reserve:** without it, actual spend is 86.5–86.9% of the allocation. The reserve is 13.5% of
  the need, and it tips the balance.

So gate (f) is a knife-edge that any of the four levers repairs; the question is which one distorts least. Gate (d) is
a ~10% scale failure that only V, or equivalently all money values, can repair. **Only a money-scale change repairs
both.**

**The oracle's other failures.**
- Gate (b), T04 and T10 urgent: these cells were P before the pilot at the same constants and are ambiguous after it.
  That follows from the same money shift.
- T01 and T07 urgent were already ambiguous at these unrepaired constants before the pilot. The design needed its
  document-latency repair step for them.
- Gate (e), empty P_urgent and twin sets, follows from (b).
- Persistence over the 343 candidates:
  - the (d) best-fitness failure in each of the seven urgent cells, and each (f) failure, occurs in **343/343**;
  - (b) occurs in 14–21;
  - (e) occurs in 14.

**Persistence over the 343 pre-registered mechanical-repair candidates**

| violation | candidates in which it occurs |
|---|---|
| (sets) e | 14 |
| T01|urgent b | 21 |
| T01|urgent d best<0.5 | 343 |
| T01|urgent d solo<0.3 | 336 |
| T03|relaxed f | 343 |
| T03|urgent d best<0.5 | 7 |
| T03|urgent f | 343 |
| T04|urgent b | 14 |
| T04|urgent d best<0.5 | 343 |
| T04|urgent d solo<0.3 | 343 |
| T07|urgent b | 14 |
| T07|urgent d best<0.5 | 343 |
| T07|urgent d solo<0.3 | 336 |
| T09|relaxed f | 343 |
| T09|urgent d best<0.5 | 343 |
| T09|urgent d solo<0.3 | 294 |
| T09|urgent f | 343 |
| T10|urgent b | 14 |
| T10|urgent d best<0.5 | 343 |
| T10|urgent d solo<0.3 | 343 |
| T12|urgent d best<0.5 | 343 |
| T12|urgent d solo<0.3 | 315 |
| T15|urgent d best<0.5 | 343 |
| T15|urgent d solo<0.3 | 294 |

**What the pilot changed, over all 256 base-point oracle organizations (pilot ÷ pre-pilot assumptions)**

| quantity | min | p10 | median | p90 | max |
|---|---|---|---|---|---|
| money ratio | 1.016 | 1.378 | 1.3925 | 1.422 | 1.461 |
| solo money ratio | 1.382 | 1.385 | 1.4208 | 1.460 | 1.461 |
| division money ratio | 1.016 | 1.375 | 1.3920 | 1.412 | 1.428 |
| elapsed ratio | 0.615 | 0.851 | 0.9254 | 0.977 | 0.988 |

## 4. Sensitivity-analysis methodology

**How each candidate is evaluated.** A candidate is a set of constant changes. Each runs through:
1. **The unrepaired gate:** the 18-point grid around the pilot's base, at the candidate's constants.
2. **The complete, unchanged pre-registered freeze:**
   - the pilot adjustments;
   - mechanical repair over 7 × 7 × 7 (document, urgent, relaxed) steps, each needing the gate on an exact
     re-simulation;
   - then the criteria check: 200 simulations per policy, R ∈ {3, 5, 8, 10}, pilot accuracy 1.0 and cost CV 0.25.

   The first candidate that passes is "frozen".

For every frozen candidate the study also reports:
- set sizes and minimum margins;
- supported rates at the chosen R;
- agreement with the **pre-pilot reference** (the provisional freeze). Its criteria check is recomputed at the same
  accuracy (1.0) and with the same sorted bootstrap;
- the §6 degeneracy checks.

**Families tested**, with 68 candidates in total. The factor **m = 1.392** is the oracle-derived money multiplier.

| family | values |
|---|---|
| 1. B | 1.00, 1.25, 1.5, 2, 2.5, 3; plus m |
| 2. V | 0.5, 0.625, 0.75, 1, 1.25, 1.5; plus 0.5 m |
| 3. B and V jointly | ×1.0, 1.25, 1.5, 1.75, 2, 2.25, 2.5; plus m |
| 3′. B, V and VoT jointly ("currency rescaling") | ×1.25, 1.3, 1.35, m, 1.45, 1.5, 1.6, 1.75, 2, 2.5 |
| 4. Fixed share | 0.5 (baseline), 0.6, 0.7, 0.8; also with joint ×1.5, ×2 and m |
| 5. K | 8 (baseline), 7, 6, 4; also with joint ×1.5, ×2 and m |
| Minimal cross-mechanism pairs | V to repair (d), with B, share or K to repair (f) |

**What each lever does.**
- **B.** B enters feasibility and the fixed rule's per-child allocation, which is proportional to the parent's balance.
  It also enters `max_tokens` capping near exhaustion and the displayed balance. It does **not** enter fitness, which
  charges money spent, not money held. So it moves no label and cannot repair (d).
- **V.** V divides every cost term. Raising V lifts all fitness levels, which repairs (d). But it shrinks every margin
  in fitness units, while δ = 0.03 stays fixed: the dollar margin needed for a label is δ·V, which is $0.015 at V = 0.5
  and $0.03 at V = 1. Money-driven S margins, about $0.02–0.03 at the pilot's costs, then fall below δ, so gates (a) and
  (c) fail at V ≥ 1. V does nothing for (f).
- **B and V jointly.** B repairs (f) and V repairs (d). But the time-for-value rate VoT/V falls by 1/s, which dilutes
  time pressure. The parallel urgent cells lose P, so (b) and (e) fail, and repair needs one urgent-VoT step. From ×1.75
  on, (a), (b) and (c) fail. At ×2 the unrepaired labels collapse to 8 S / 0 P / 22 ambiguous, because every relaxed
  cell loses S.
- **B, V and VoT jointly.**
  - It preserves VoT/V exactly.
  - At the median organization, it brings money/V back to the design's level: best-organization money/V is a median
    0.071, against 0.070 in the design.
  - In fitness and feasibility it is **economically identical to dividing every price and fee by s**, while the agent
    keeps seeing real list prices.
  - Against list prices, the price of time rises by s. That exactly offsets the pilot's measured rise in money per unit
    of work.
  - Fees, which the pilot did not change, become 1/s as large relative to V as designed.
  - It repairs (d) and (f) with no repair step.
- **Share.** Raising the share repairs (f) (≥ 0.503 is enough) but not (d). It changes `central`'s defining rule, which
  is the thing criterion 5 compares against.
- **K.** K ≤ 7 removes `atstart8`, which repairs (f), but not (d). K is the concurrency cap for every mode, so this
  shrinks every mode's action space.

## 5. Full candidate comparison

**Every candidate: unrepaired gate and the unchanged pre-registered freeze**

`steps` = mechanical repair (doc steps, urgent VoT steps, relaxed VoT steps) of the first candidate that passes the gate and the criteria check.

| candidate | family | B | V | VoT × | share | K | unrepaired gate | freeze | steps | R |
|---|---|---|---|---|---|---|---|---|---|---|
| E0 (as pre-registered) | baseline | 1 | 0.5 | 1 | 0.5 | 8 | fails b,d,e,f | none | - | - |
| B=1.25 | 1 budget | 1.25 | 0.5 | 1 | 0.5 | 8 | fails b,d,e | none | - | - |
| B=1.5 | 1 budget | 1.5 | 0.5 | 1 | 0.5 | 8 | fails b,d,e | none | - | - |
| B=2 | 1 budget | 2 | 0.5 | 1 | 0.5 | 8 | fails b,d,e | none | - | - |
| B=2.5 | 1 budget | 2.5 | 0.5 | 1 | 0.5 | 8 | fails b,d,e | none | - | - |
| B=3 | 1 budget | 3 | 0.5 | 1 | 0.5 | 8 | fails b,d,e | none | - | - |
| V=0.625 | 2 value | 1 | 0.625 | 1 | 0.5 | 8 | fails b,e,f | none | - | - |
| V=0.75 | 2 value | 1 | 0.75 | 1 | 0.5 | 8 | fails b,e,f | none | - | - |
| V=1 | 2 value | 1 | 1 | 1 | 0.5 | 8 | fails a,b,c,e,f | none | - | - |
| V=1.25 | 2 value | 1 | 1.25 | 1 | 0.5 | 8 | fails a,b,c,e,f | none | - | - |
| V=1.5 | 2 value | 1 | 1.5 | 1 | 0.5 | 8 | fails a,b,c,e,f | none | - | - |
| B,V x1.25 | 3 joint | 1.25 | 0.625 | 1 | 0.5 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| B,V x1.5 | 3 joint | 1.5 | 0.75 | 1 | 0.5 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| B,V x1.75 | 3 joint | 1.75 | 0.875 | 1 | 0.5 | 8 | fails a,b,c,e | none | - | - |
| B,V x2 | 3 joint | 2 | 1 | 1 | 0.5 | 8 | fails a,b,c,e | none | - | - |
| B,V x2.25 | 3 joint | 2.25 | 1.125 | 1 | 0.5 | 8 | fails a,b,c,e | none | - | - |
| B,V x2.5 | 3 joint | 2.5 | 1.25 | 1 | 0.5 | 8 | fails a,b,c,e | none | - | - |
| B,V,VoT x1.5 | 3' currency | 1.5 | 0.75 | 1.5 | 0.5 | 8 | PASS | frozen | (0, 0, 0) | 3 |
| B,V,VoT x2 | 3' currency | 2 | 1 | 2 | 0.5 | 8 | fails a,b,c,e | none | - | - |
| B,V,VoT x2.5 | 3' currency | 2.5 | 1.25 | 2.5 | 0.5 | 8 | fails a,b,c,e | none | - | - |
| share=0.6 | 4 share | 1 | 0.5 | 1 | 0.6 | 8 | fails b,d,e | none | - | - |
| share=0.7 | 4 share | 1 | 0.5 | 1 | 0.7 | 8 | fails b,d,e | none | - | - |
| share=0.8 | 4 share | 1 | 0.5 | 1 | 0.8 | 8 | fails b,d,e | none | - | - |
| K=7 | 5 K | 1 | 0.5 | 1 | 0.5 | 7 | fails b,d,e | none | - | - |
| K=6 | 5 K | 1 | 0.5 | 1 | 0.5 | 6 | fails b,d,e | none | - | - |
| K=4 | 5 K | 1 | 0.5 | 1 | 0.5 | 4 | fails b,d,e | none | - | - |
| B,V x1.5 + share=0.6 | D joint+share | 1.5 | 0.75 | 1 | 0.6 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| B,V x1.5 + share=0.7 | D joint+share | 1.5 | 0.75 | 1 | 0.7 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| B,V x1.5 + share=0.8 | D joint+share | 1.5 | 0.75 | 1 | 0.8 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| B,V x1.5 + K=7 | E joint+K | 1.5 | 0.75 | 1 | 0.5 | 7 | fails b,e | frozen | (0, 1, 0) | 5 |
| B,V x1.5 + K=6 | E joint+K | 1.5 | 0.75 | 1 | 0.5 | 6 | fails b,e | frozen | (0, 1, 0) | 5 |
| B,V x1.5 + K=4 | E joint+K | 1.5 | 0.75 | 1 | 0.5 | 4 | fails b,e | frozen | (0, 1, 0) | 5 |
| B,V x2 + share=0.6 | D joint+share | 2 | 1 | 1 | 0.6 | 8 | fails a,b,c,e | none | - | - |
| B,V x2 + share=0.7 | D joint+share | 2 | 1 | 1 | 0.7 | 8 | fails a,b,c,e | none | - | - |
| B,V x2 + share=0.8 | D joint+share | 2 | 1 | 1 | 0.8 | 8 | fails a,b,c,e | none | - | - |
| B,V x2 + K=7 | E joint+K | 2 | 1 | 1 | 0.5 | 7 | fails a,b,c,e | none | - | - |
| B,V x2 + K=6 | E joint+K | 2 | 1 | 1 | 0.5 | 6 | fails a,b,c,e | none | - | - |
| B,V x2 + K=4 | E joint+K | 2 | 1 | 1 | 0.5 | 4 | fails a,b,c,e | none | - | - |
| A: B x1.392 | A at m | 1.392 | 0.5 | 1 | 0.5 | 8 | fails b,d,e | none | - | - |
| B: V x1.392 | B at m | 1 | 0.696 | 1 | 0.5 | 8 | fails b,e,f | none | - | - |
| C: B,V x1.392 | C at m | 1.392 | 0.696 | 1 | 0.5 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| C': B,V,VoT x1.392 | C' at m | 1.392 | 0.696 | 1.392 | 0.5 | 8 | PASS | frozen | (0, 0, 0) | 3 |
| D: B,V x1.392 + share=0.6 | D at m | 1.392 | 0.696 | 1 | 0.6 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| D: B,V x1.392 + share=0.7 | D at m | 1.392 | 0.696 | 1 | 0.7 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| E: B,V x1.392 + K=7 | E at m | 1.392 | 0.696 | 1 | 0.5 | 7 | fails b,e | frozen | (0, 1, 0) | 5 |
| E: B,V x1.392 + K=6 | E at m | 1.392 | 0.696 | 1 | 0.5 | 6 | fails b,e | frozen | (0, 1, 0) | 5 |
| E: B,V x1.392 + K=4 | E at m | 1.392 | 0.696 | 1 | 0.5 | 4 | fails b,e | frozen | (0, 1, 0) | 5 |
| D': B,V,VoT x1.392 + share=0.6 | D' at m | 1.392 | 0.696 | 1.392 | 0.6 | 8 | PASS | frozen | (0, 0, 0) | 3 |
| D': B,V,VoT x1.392 + share=0.7 | D' at m | 1.392 | 0.696 | 1.392 | 0.7 | 8 | PASS | frozen | (0, 0, 0) | 3 |
| E': B,V,VoT x1.392 + K=7 | E' at m | 1.392 | 0.696 | 1.392 | 0.5 | 7 | PASS | frozen | (0, 0, 0) | 3 |
| E': B,V,VoT x1.392 + K=6 | E' at m | 1.392 | 0.696 | 1.392 | 0.5 | 6 | PASS | frozen | (0, 0, 0) | 3 |
| E': B,V,VoT x1.392 + K=4 | E' at m | 1.392 | 0.696 | 1.392 | 0.5 | 4 | PASS | frozen | (0, 0, 0) | 3 |
| B,V,VoT x1.25 | 3' currency | 1.25 | 0.625 | 1.25 | 0.5 | 8 | PASS | frozen | (0, 0, 0) | 5 |
| B,V,VoT x1.3 | 3' currency | 1.3 | 0.65 | 1.3 | 0.5 | 8 | PASS | frozen | (0, 0, 0) | 3 |
| B,V,VoT x1.35 | 3' currency | 1.35 | 0.675 | 1.35 | 0.5 | 8 | PASS | frozen | (0, 0, 0) | 3 |
| B,V,VoT x1.45 | 3' currency | 1.45 | 0.725 | 1.45 | 0.5 | 8 | PASS | frozen | (0, 0, 0) | 3 |
| B,V,VoT x1.6 | 3' currency | 1.6 | 0.8 | 1.6 | 0.5 | 8 | PASS | frozen | (0, 0, 0) | 3 |
| B,V,VoT x1.75 | 3' currency | 1.75 | 0.875 | 1.75 | 0.5 | 8 | fails a,b,c | none | - | - |
| V=0.75 + B=2 | B x V | 2 | 0.75 | 1 | 0.5 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| V=1 + B=1.5 | B x V | 1.5 | 1 | 1 | 0.5 | 8 | fails a,b,c,e | none | - | - |
| V=0.75 + share=0.7 | V+share | 1 | 0.75 | 1 | 0.7 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| V=0.75 + share=0.8 | V+share | 1 | 0.75 | 1 | 0.8 | 8 | fails b,e | frozen | (0, 1, 0) | 5 |
| V=1 + share=0.7 | V+share | 1 | 1 | 1 | 0.7 | 8 | fails a,b,c,e | none | - | - |
| V=1 + share=0.8 | V+share | 1 | 1 | 1 | 0.8 | 8 | fails a,b,c,e | none | - | - |
| V=0.75 + K=7 | V+K | 1 | 0.75 | 1 | 0.5 | 7 | fails b,e | frozen | (0, 1, 0) | 5 |
| V=0.75 + K=6 | V+K | 1 | 0.75 | 1 | 0.5 | 6 | fails b,e | frozen | (0, 1, 0) | 5 |
| V=1 + K=7 | V+K | 1 | 1 | 1 | 0.5 | 7 | fails a,b,c,e | none | - | - |
| V=1 + K=6 | V+K | 1 | 1 | 1 | 0.5 | 6 | fails a,b,c,e | none | - | - |

**Viable candidates (the freeze succeeds)**

Reference = the provisional pre-pilot freeze (r = 1), the geometry Experiment 0 was designed to have; its criteria check is recomputed here at the pilot's accuracy (1.0) like every candidate. Rates are the criteria check's 'supported' rates at the chosen R (200 simulations each), with the bootstrap's cells in sorted order (amendment 0b-0), so they do not depend on PYTHONHASHSEED.

| candidate | S/P/amb | S_urg | P_urg | twin | D_urg | I | min S margin | min P margin | R | IDEAL | NEVER | ALWAYS | RANDOM | IFF-URGENT | IFF-MULTIDOC | WASTEFUL | labels = ref | mean abs Δ fitness vs ref |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **reference (pre-pilot, r = 1)** | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.034 | 0.041 | 3 | 0.835 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | - | - |
| B,V x1.25 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.039 | 0.052 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0075 |
| B,V x1.5 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| B,V,VoT x1.5 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.033 | 0.090 | 3 | 0.895 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | 30/30 | 0.0170 |
| B,V x1.5 + share=0.6 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| B,V x1.5 + share=0.7 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| B,V x1.5 + share=0.8 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| B,V x1.5 + K=7 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| B,V x1.5 + K=6 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| B,V x1.5 + K=4 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| C: B,V x1.392 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.046 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0212 |
| C': B,V,VoT x1.392 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.076 | 3 | 0.855 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | 30/30 | 0.0097 |
| D: B,V x1.392 + share=0.6 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.046 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0212 |
| D: B,V x1.392 + share=0.7 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.046 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0212 |
| E: B,V x1.392 + K=7 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.046 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0212 |
| E: B,V x1.392 + K=6 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.046 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0212 |
| E: B,V x1.392 + K=4 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.046 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0212 |
| D': B,V,VoT x1.392 + share=0.6 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.076 | 3 | 0.855 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | 30/30 | 0.0097 |
| D': B,V,VoT x1.392 + share=0.7 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.076 | 3 | 0.855 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | 30/30 | 0.0097 |
| E': B,V,VoT x1.392 + K=7 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.076 | 3 | 0.855 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | 30/30 | 0.0097 |
| E': B,V,VoT x1.392 + K=6 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.076 | 3 | 0.855 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | 30/30 | 0.0097 |
| E': B,V,VoT x1.392 + K=4 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.035 | 0.076 | 3 | 0.855 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | 30/30 | 0.0097 |
| B,V,VoT x1.25 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.039 | 0.052 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0091 |
| B,V,VoT x1.3 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.037 | 0.059 | 3 | 0.800 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | 30/30 | 0.0081 |
| B,V,VoT x1.35 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.036 | 0.068 | 3 | 0.820 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | 30/30 | 0.0086 |
| B,V,VoT x1.45 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.034 | 0.085 | 3 | 0.870 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.005 | 30/30 | 0.0136 |
| B,V,VoT x1.6 | 23/5/2 | 8 | 5 | 10 | 3 | 0 | 0.031 | 0.033 | 3 | 0.950 | 0.000 | 0.000 | 0.005 | 0.000 | 0.000 | 0.005 | 29/30 | 0.0233 |
| V=0.75 + B=2 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| V=0.75 + share=0.7 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| V=0.75 + share=0.8 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| V=0.75 + K=7 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |
| V=0.75 + K=6 | 23/4/3 | 8 | 4 | 8 | 3 | 0 | 0.032 | 0.043 | 5 | 0.940 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 30/30 | 0.0354 |

**Every viable candidate has the reference's label structure:** 23 S, 4 P, 3 ambiguous; twin 8, D_urgent 3, I 0. The
one exception is currency ×1.6, which gains a fifth P cell (T12 urgent), so it agrees with the reference on 29 of 30
cells. The candidates differ in five ways:
- whether repair is needed: currency rescaling needs none, joint B,V needs one urgent-VoT step;
- R: 3 for currency rescaling on s ∈ [1.3, 1.6], 5 at 1.25 and for every joint-B,V candidate;
- the minimum P margin: 0.076 for C′ against 0.046 for C, D and E at m;
- distance from the reference;
- how many mechanisms they touch.

## 6. Degeneracy checks

**Degeneracy checks (viable candidates, base point)**

| candidate | P cells | S cells | S/P margins < 2δ | S left at δ = 0.045 (diagnostic) | median fitness spread over orgs | median best money / V (range) | median best money + time / V | min fixed-rule allocation / child need | children fundable at the child need | best k in P cells | fitness lost at k = 1 / largest k on the route | max child lifetime used |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **reference (pre-pilot, r = 1)** | 4 | 23 | 27 | 8 | 0.310 | 0.070 (0.040–0.283) | 0.128 | 3.26 | 24 | [3, 4] | 0.28–0.29 / 0.05–0.12 | 14% |
| B,V x1.25 | 4 | 23 | 26 | 8 | 0.319 | 0.080 (0.044–0.314) | 0.131 | 3.26 | 24 | [3, 4] | 0.26–0.26 / 0.06–0.14 | 13% |
| B,V x1.5 | 4 | 23 | 27 | 0 | 0.266 | 0.066 (0.037–0.261) | 0.109 | 3.93 | 30 | [3, 4] | 0.21–0.22 / 0.05–0.11 | 13% |
| B,V,VoT x1.5 | 4 | 23 | 23 | 7 | 0.292 | 0.066 (0.037–0.261) | 0.121 | 3.93 | 30 | [3, 4] | 0.27–0.29 / 0.04–0.10 | 13% |
| B,V x1.5 + share=0.6 | 4 | 23 | 27 | 0 | 0.266 | 0.066 (0.037–0.261) | 0.109 | 4.72 | 30 | [3, 4] | 0.21–0.22 / 0.05–0.11 | 13% |
| B,V x1.5 + share=0.7 | 4 | 23 | 27 | 0 | 0.266 | 0.066 (0.037–0.261) | 0.109 | 5.50 | 30 | [3, 4] | 0.21–0.22 / 0.05–0.11 | 13% |
| B,V x1.5 + share=0.8 | 4 | 23 | 27 | 0 | 0.266 | 0.066 (0.037–0.261) | 0.109 | 6.29 | 30 | [3, 4] | 0.21–0.22 / 0.05–0.11 | 13% |
| B,V x1.5 + K=7 | 4 | 23 | 27 | 0 | 0.248 | 0.066 (0.037–0.261) | 0.109 | 3.93 | 30 | [3, 4] | 0.21–0.22 / 0.05–0.13 | 13% |
| B,V x1.5 + K=6 | 4 | 23 | 27 | 0 | 0.229 | 0.066 (0.037–0.261) | 0.109 | 3.93 | 30 | [3, 4] | 0.21–0.22 / 0.05–0.08 | 13% |
| B,V x1.5 + K=4 | 4 | 23 | 27 | 0 | 0.199 | 0.066 (0.037–0.261) | 0.109 | 3.93 | 30 | [3, 4] | 0.21–0.22 / 0.00–0.04 | 13% |
| C: B,V x1.392 | 4 | 23 | 27 | 8 | 0.287 | 0.071 (0.040–0.282) | 0.118 | 3.64 | 27 | [3, 4] | 0.23–0.24 / 0.06–0.12 | 13% |
| C': B,V,VoT x1.392 | 4 | 23 | 23 | 8 | 0.300 | 0.071 (0.040–0.282) | 0.127 | 3.64 | 27 | [3, 4] | 0.27–0.28 / 0.05–0.12 | 13% |
| D: B,V x1.392 + share=0.6 | 4 | 23 | 27 | 8 | 0.287 | 0.071 (0.040–0.282) | 0.118 | 4.37 | 27 | [3, 4] | 0.23–0.24 / 0.06–0.12 | 13% |
| D: B,V x1.392 + share=0.7 | 4 | 23 | 27 | 8 | 0.287 | 0.071 (0.040–0.282) | 0.118 | 5.10 | 27 | [3, 4] | 0.23–0.24 / 0.06–0.12 | 13% |
| E: B,V x1.392 + K=7 | 4 | 23 | 27 | 8 | 0.268 | 0.071 (0.040–0.282) | 0.118 | 3.64 | 27 | [3, 4] | 0.23–0.24 / 0.06–0.14 | 13% |
| E: B,V x1.392 + K=6 | 4 | 23 | 27 | 8 | 0.247 | 0.071 (0.040–0.282) | 0.118 | 3.64 | 27 | [3, 4] | 0.23–0.24 / 0.06–0.09 | 13% |
| E: B,V x1.392 + K=4 | 4 | 23 | 27 | 8 | 0.215 | 0.071 (0.040–0.282) | 0.118 | 3.64 | 27 | [3, 4] | 0.23–0.24 / 0.00–0.04 | 13% |
| D': B,V,VoT x1.392 + share=0.6 | 4 | 23 | 23 | 8 | 0.300 | 0.071 (0.040–0.282) | 0.127 | 4.37 | 27 | [3, 4] | 0.27–0.28 / 0.05–0.12 | 13% |
| D': B,V,VoT x1.392 + share=0.7 | 4 | 23 | 23 | 8 | 0.300 | 0.071 (0.040–0.282) | 0.127 | 5.10 | 27 | [3, 4] | 0.27–0.28 / 0.05–0.12 | 13% |
| E': B,V,VoT x1.392 + K=7 | 4 | 23 | 23 | 8 | 0.280 | 0.071 (0.040–0.282) | 0.127 | 3.64 | 27 | [3, 4] | 0.27–0.28 / 0.05–0.14 | 13% |
| E': B,V,VoT x1.392 + K=6 | 4 | 23 | 23 | 8 | 0.267 | 0.071 (0.040–0.282) | 0.127 | 3.64 | 27 | [3, 4] | 0.27–0.28 / 0.05–0.09 | 13% |
| E': B,V,VoT x1.392 + K=4 | 4 | 23 | 23 | 8 | 0.216 | 0.071 (0.040–0.282) | 0.127 | 3.64 | 27 | [3, 4] | 0.27–0.28 / 0.00–0.04 | 13% |
| B,V,VoT x1.25 | 4 | 23 | 26 | 8 | 0.317 | 0.080 (0.044–0.314) | 0.135 | 3.26 | 24 | [3, 4] | 0.26–0.26 / 0.06–0.14 | 13% |
| B,V,VoT x1.3 | 4 | 23 | 24 | 8 | 0.308 | 0.076 (0.043–0.302) | 0.132 | 3.40 | 25 | [3, 4] | 0.26–0.27 / 0.06–0.13 | 13% |
| B,V,VoT x1.35 | 4 | 23 | 23 | 8 | 0.304 | 0.074 (0.041–0.291) | 0.129 | 3.53 | 26 | [3, 4] | 0.26–0.27 / 0.05–0.12 | 13% |
| B,V,VoT x1.45 | 4 | 23 | 23 | 8 | 0.296 | 0.069 (0.038–0.271) | 0.124 | 3.80 | 29 | [3, 4] | 0.27–0.28 / 0.04–0.11 | 13% |
| B,V,VoT x1.6 | 5 | 23 | 24 | 1 | 0.279 | 0.062 (0.035–0.245) | 0.117 | 4.20 | 32 | [3, 4] | 0.28–0.29 / 0.03–0.09 | 13% |
| V=0.75 + B=2 | 4 | 23 | 27 | 0 | 0.266 | 0.066 (0.037–0.261) | 0.109 | 5.26 | 40 | [3, 4] | 0.21–0.22 / 0.05–0.11 | 13% |
| V=0.75 + share=0.7 | 4 | 23 | 27 | 0 | 0.266 | 0.066 (0.037–0.261) | 0.109 | 3.64 | 19 | [3, 4] | 0.21–0.22 / 0.05–0.11 | 13% |
| V=0.75 + share=0.8 | 4 | 23 | 27 | 0 | 0.266 | 0.066 (0.037–0.261) | 0.109 | 4.16 | 19 | [3, 4] | 0.21–0.22 / 0.05–0.11 | 13% |
| V=0.75 + K=7 | 4 | 23 | 27 | 0 | 0.248 | 0.066 (0.037–0.261) | 0.109 | 2.60 | 19 | [3, 4] | 0.21–0.22 / 0.05–0.13 | 13% |
| V=0.75 + K=6 | 4 | 23 | 27 | 0 | 0.229 | 0.066 (0.037–0.261) | 0.109 | 2.60 | 19 | [3, 4] | 0.21–0.22 / 0.05–0.08 | 13% |

**Division is not nearly always optimal, and solo is not nearly always optimal.** Division pays in 4 of 30 cells, solo
in 23, with 3 ambiguous. That is the design exactly. Few P cells and no I cells were already listed in Experiment 0's
known limitations. 0b neither fixes nor worsens them.

**Monetary scarcity is restored exactly.**
- Under C′ the best organization's money is a median **0.071 of V** (0.040–0.282), against 0.070 (0.040–0.283) in the
  design.
- Money plus time is 0.127, against 0.128.
- Fitness spread across organizations is a median 0.30, against 0.31.
- Scarcity acts through fitness, not as a hard constraint. At the minimum viable per-child allocation the root could
  fund ≥ 27 children, against 24 in the design and K = 8. So the budget does not bind the best organizations, in 0b or
  in the design.
- Options that add share or B changes raise this slack further (4–6× the child need).

**Child budget choices still matter, but only as a floor.**
- A child needs about $0.037–$0.049. Allocating less starves it.
- Over-allocation is refunded at no cost.
- This one-sided exposure is inherited from the design. Making it two-sided would need a new mechanism, which is out
  of scope.

**K and topology.**
- At K = 8 the best fan-out in P cells is **interior** (k = 3–4).
- Choosing k = 1 costs 0.27–0.28 of fitness; choosing the largest k on the route costs 0.05–0.12. So "how many
  children" is a real decision.
- At K = 4 the optimum reaches the cap in T04 and T10 (the loss at the largest k is 0.00–0.04), which partly
  predetermines the architecture. **K = 4 is rejected on that ground.**
- K = 6 or 7 does not predetermine the topology, but it buys nothing once the money scale is fixed.

**V is not so high that efficiency stops mattering.**
- The best organization's money and time are 0.127 of V, and the fitness spread is 0.30, equal to the design.
- V ≥ 1 (families 2 and 3) is where efficiency margins drop below δ and S labels vanish. Those candidates fail the gate.

**Threshold placement.**
- **S labels are thin by design.** Solo beats a one-child fan-out by a spawn's overhead, about 0.035–0.05 of V. 23 of
  the 27 S/P labels are within 2δ, against 27 in the design. 8 S remain at a diagnostic δ = 0.045, the same as the
  design. Every S nevertheless holds at all 18 grid points, and 0b does not use this thinness to create labels.
- **P labels are more robust than designed.** The minimum P margin is 0.076, against 0.041, and all 4 P cells survive a
  diagnostic δ = 0.06, against 2 of 4 surviving δ = 0.045 in the design.
  - The widening comes from the pilot's changed relative physics: solo money rose 1.42× against 1.39× for divisions,
    and the reasoning perturbation narrowed around 36 tokens. Together with money/V restored, this makes division's
    advantage in the parallel urgent cells clearer than designed.
  - It grows with s along the plateau (0.052 at 1.25, 0.076 at 1.392, 0.085 at 1.45).
  - s is fixed by the rule in §8, not chosen for this margin.
  - The widening makes P cells easier to recognise for any policy. It does not relax any criterion.

**The developmental agent still has to reason about each lifecycle decision:**

| decision | still exposed? | why |
|---|---|---|
| whether to divide | yes | S and P cells both exist, with twin and dissociation cells |
| how many children | yes | the optimum is interior and a wrong k costs 0.05–0.28 |
| how much budget | as a floor only | as above |
| how long children live | weakly | children use ≤ 13% of the fixed-rule lifetime (14% in the design), so only absurdly short lifetimes bind |

The lifetime weakness is inherited and stated as a limitation, not repaired.

## 7. Options and ranked shortlist

**The eight distortion principles used for the ranking** are the ones you set:
1. preserve the research question;
2. restore viability, not manufacture a developmental advantage;
3. leave task content untouched;
4. preserve meaningful resource scarcity;
5. keep environments where division pays and where it does not;
6. minimize mechanism changes;
7. justify changes from pilot-measured physics, not outcome tuning;
8. keep the developmental policy exposed to allocation decisions.

**The main options, compared at m = 1.392:**

| option | fixes | incentive change | scientific distortion | solo/division boundary |
|---|---|---|---|---|
| **A: B only** | (f) | none | minimal, but **fails (b), (d), (e)** | n/a (no freeze) |
| **B: V only** | (d) | VoT/V ÷ 1.392 | **fails (b), (e), (f)**; δ-margins shrink | n/a |
| **C: B and V** | (d), (f); plus 1 urgent-VoT repair step | relaxed VoT/V ÷ 1.392; urgent VoT/V ÷ 1.392 × 1.25 | the two regimes' time-for-value rates move differently; P margins 0.046; R = 5 | preserved (30/30) |
| **C′: B, V and VoT** | (d), (f); no repair | VoT/V unchanged; money/V back to the design (median); relative to list prices, time is s dearer and fees s cheaper | a price-level rescaling that undoes the pilot's measured cost rise; units no longer equal list-price dollars | preserved (30/30), 23/4/3 |
| **D: C plus share 0.6/0.7** | as C | also changes `central`'s rule | changes criterion 5's comparator for no benefit (identical labels and R) | preserved |
| **E: C plus K 7/6/4** | as C | shrinks every mode's action space | removes topologies for no benefit; K = 4 puts the optimum at the cap | preserved (K = 4 degenerates) |
| D′/E′: C′ plus share or K | as C′ | as D/E | pure added distortion (identical labels and R to C′) | preserved |

**Ranked shortlist.** Every viable candidate satisfies principles 1, 3 and 5. The ranking uses principles 2, 4, 6, 7
and 8 **without** the criteria-check outputs. R and IDEAL rates are pre-registered power diagnostics; here they break
ties only on run cost.

1. **C′: B, V and VoT × 1.392.**
   - It moves no time-for-value rate and needs no repair (principle 2).
   - It restores money scarcity to the design's level, 0.071 against 0.070 (principle 4).
   - It is one scalar and adds no mechanism (principle 6).
   - s comes from a fixed rule on the pilot's statistics. The whole plateau s ∈ [1.25, 1.6] passes, with identical
     labels on [1.25, 1.5], so 1.392 is not a threshold edge (principle 7).
   - Allocation exposure is unchanged (principle 8).
   - Its R = 3 matches the design's.
2. **C′ at a round neighbour, for example ×1.35 or ×1.45.** Equally viable, with R = 3, but not derived from the pilot.
3. **C: B and V × 1.392, plus the pre-registered urgent-VoT step.**
   - Viable, and preserves the labels.
   - But the two regimes' time-for-value rates move by different factors (principle 2), and it needs a repair step.
   - B, V × 1.25 with the same repair step is closest to the design in pooled fitness (mean |Δ| 0.0075, against 0.0097
     for C′), but its scale is not derived from the pilot, and it also changes the time-for-value rate.
   - These rank below C′ whatever R is. They also need R = 5, which is 1.7× the main run.
4. **V ≈ 0.75, plus B, share or K for (f).** Two knobs are chosen separately for two failures, V = 0.75 is not derived,
   VoT/V is diluted, and R = 5.
5. **Rejected:**
   - D, E, D′ and E′: extra distortion without benefit; K = 4 is also degenerate.
   - Every non-viable option: B only, V only, share only, K only, joint ≥ 1.75, and currency ≥ 1.75.

## 8. Recommended Experiment 0b configuration

One configuration: **C′, currency rescaling by the oracle-derived money multiplier s = 1.392.**

| constant | Experiment 0 | **Experiment 0b** | why it changes | pilot fact | gate failure repaired | nature of change |
|---|---|---|---|---|---|---|
| run budget B (both regimes) | $1.00 | **$1.392** | children's needs rose with token costs; keeps the design's budget-to-cost ratio | r = 2.0052 and 36 reasoning tokens → money × 1.392 | (f): `atstart8` per-child allocation $0.0843–$0.0844 against a need of $0.0599–$0.0601 | absolute scale |
| task value V (both regimes) | $0.50 | **$0.696** | money/V back to its designed level | same | (d): best urgent fitness 0.548–0.575 (≥ 0.5); solo T04/T10 urgent 0.335 (≥ 0.3) | absolute scale, relative to list prices |
| value of time, relaxed | 0.00005 $/s | **0.0000696 $/s** | keeps VoT/V, the time-for-value rate, exactly as designed | same | prevents (b)/(e) without repair | absolute scale |
| value of time, urgent | 0.0008 $/s | **0.0011136 $/s** | as above | same | as above | absolute scale |
| fixed allocation share | 0.5 | **0.5 (unchanged)** | not needed | - | - | - |
| K (max concurrency − 1) | 8 | **8 (unchanged)** | not needed; lowering it restricts the architecture | - | - | - |
| every other constant | - | **unchanged** | - | - | - | - |

Taken together the change alters absolute scale only. It changes no designed relative incentive (VoT/V; money/V at the
median) and no topology. Relative to list prices, time costs s more and fees s less, which offsets the pilot's measured
cost shift.

Unchanged constants include: deadline 1500 s, failure penalty 1.0, prices, fees, latencies, document latency 0.100 s per
token (the pre-registered repair may still move it; C′ needs none), `min_step_tokens` 256 (from the pilot), lifetime
share 0.6, and every cap.

**Derivation of s**, reproducible with `study.py money_multiplier()`.
- s is the median, over all 256 base-point oracle organizations at Experiment 0's constants, of money(r = 2.0052, 36
  reasoning tokens) ÷ money(r = 1, 150 reasoning tokens).
- The value is 1.392499, which is 1.392 to three decimals.
- Its only inputs are the two measured pilot statistics and the unchanged oracle. No calibration outcome enters it.
- Alternative statistics of the same ratio all fall on the R = 3 plateau [1.3, 1.6]: the division median is 1.392, the
  solo median 1.421, and p10–p90 run from 1.378 to 1.422.

**Outcome under the unchanged pre-registered freeze**, with the sorted bootstrap (0b-0):

| check | result |
|---|---|
| gate (a)–(f) | **pass**, with repair steps (0, 0, 0) |
| labels | S 23 / P 4 / ambiguous 3 (S_relaxed 15, S_urgent 8, P_urgent 4, P_relaxed 0) |
| sets | twin 8, D_urgent 3, I 0 |
| minimum margins | S 0.035, P 0.076 |
| criteria check | **R = 3** |
| supported rate at R = 3 | IDEAL 0.855; NEVER 0.000, ALWAYS 0.000, RANDOM 0.000, SPAWN-IFF-URGENT 0.000, SPAWN-IFF-MULTIDOC 0.000, WASTEFUL 0.005 |

**How closely it restores the designed geometry.** The design reference differs from C′ in two ways: it includes a
+0.005 s/token document-latency repair, and it was frozen at accuracy 0.9. Its criteria check is recomputed here at
accuracy 1.0.

| measure | 0b (C′) | design reference |
|---|---|---|
| label agreement | 30/30 | - |
| mean abs difference in solo fitness | 0.009 | - |
| mean abs difference in division fitness | 0.010 | - |
| mean abs difference in solo − division gap | 0.004 | - |
| minimum S margin | 0.035 | 0.034 |
| minimum P margin | 0.076 (see §6) | 0.041 |
| R | 3 | 3 |
| IDEAL supported | 0.855 | 0.835 |
| best money / V | 0.071 | 0.070 |
| children fundable | 27 | 24 |

In the urgent parallel cells specifically, best-division fitness is 0.548–0.561 under C′, against 0.527–0.540 in the
design, and solo fitness is 0.335–0.355, against 0.305–0.327.

**Your joint-scaling hypothesis**, "scale B and V by about the token multiplier", is **refuted as stated and confirmed
in a corrected form.**
- The relevant multiplier is the **money** multiplier, 1.392, not the token multiplier of about 2. Reasoning tokens
  fell and fees did not change.
- VoT must scale too. Otherwise time pressure is diluted and a repair step is needed.
- At ×2, scaling B and V fails (a), (b), (c) and (e); scaling VoT as well still fails them, because S labels collapse
  below δ.
- At the oracle-derived money multiplier, scaling all three restores the design to within about 0.01 fitness.

## 9. Scientific justification

**The environment's economics are relative.** Whether division pays depends on the exchange rates between money, time
and correct answers: V, VoT, and the prices of tokens, queries and coordination.

**The pilot shifted the price of tokens.** It showed that the oracle's organizations cost about 1.39× the money the
design assumed, per unit of work. Changing the environment's unit of account by that factor restores the designed
money/V at the median and keeps VoT/V exactly. The pilot's *relative* physics stay as measured:
- input versus output tokens;
- solo versus division money shifts (1.42× against 1.39×);
- fixed fees, which become relatively cheaper.

Those relative changes, not 0b, are what widen the P margins (§6).

**What this does not do:**
- it does not change task content, prompt templates, mechanisms, K, the allocation rule, δ, the gates or the criteria;
- it does not choose s by looking at labels, margins or R.

The same economics could be obtained by dividing every price by s. The recommendation scales the environment's dollar
values instead, so agents keep seeing real list prices.

**Researcher degrees of freedom, in the order things happened:**
1. The first sweep (families 1–5 and currency ×1.5, ×2, ×2.5) ran first.
2. While it ran, the money multiplier was computed from the pilot statistics. That was after the B-only and V-only
   results were known, and before the joint and currency results.
3. The first sweep then showed joint B,V viable only with a repair step, currency ×1.5 passing and currency ×2 failing.
4. The options at m and the finer currency grid were added afterwards.

Four things limit the risk of tuning:
1. s is fixed by a rule on pilot statistics.
2. The passing region is a plateau, s ∈ [1.25, 1.6], not a point.
3. All 68 candidates are reported, including failures.
4. No live developmental or router behaviour exists, so nothing could be tuned towards it (§12).

The criteria-check rates were not used to choose s or to rank C′ above its alternatives (§7).

## 10. Exact pre-registration amendments for Experiment 0b

The 0b pre-registration is a new document, `SPEC_0B.md`, that references SPEC.md and states only these amendments.
`SPEC.md`, `data/frozen.json` and Experiment 0's `EXPERIMENT_STATUS.md` entries stay unchanged; git history keeps them.
The 0b document, its implementation and its freeze must be committed **before** any live developmental or router run.

**Carried forward unchanged.**
- **Tasks and scoring:** task questions, answers, classes, subtypes and routes (15 main plus 3 pilot tasks); the
  grader.
- **Prompts:** prompt **templates** and MODE RULES text. The rendered values of V, VoT and balances change, so the
  prompt fingerprint is re-frozen.
- **Runtime:** lifecycle actions; event semantics; the step reserve, subject to 0b-2; metrics and the fitness formula.
- **Calibration:** δ = 0.03; gate thresholds (a)–(f); the perturbation grid; mechanical repair; the criteria check and
  its rule for choosing R.
- **Evaluation:** falsification criteria 1–5; validity conditions (i)–(vi); the bootstrap design (only its iteration
  order is fixed, by 0b-0); the H2 analysis.
- **Pilot:** the Experiment 0 live pilot and its measurements, reused and not re-run.
- **Model and environment:** `claude-opus-5-5` at effort `low`; prices, fees, latencies, deadline, caps, K = 8, fixed
  share 0.5 and lifetime share 0.6.

**Amendments.**

**0b-0. Reproducible bootstrap (infrastructure; before the freeze).**
- In `devagents/evals/analysis.py` `contrast_ci`, iterate `sorted(cells)` instead of the set.
- Add a test that the criteria check and a §8 evaluation give identical results under different `PYTHONHASHSEED`
  values.
- This changes no pre-registered rule. It makes the same bootstrap reproducible.
- If it is not done, `freeze` and `report` must at least be run with `PYTHONHASHSEED=0` recorded, but the code fix is
  preferred.

**0b-1. Constants.** This supersedes, for 0b only:
- SPEC §3.4's "V = $0.50";
- SPEC §4's regime values and the $1.00 budget;
- the header rule that constants change only through §7.4's mechanical procedure. 0b-1 is a one-time, documented,
  pre-freeze change.

The values are:
- B = $1.392 in both regimes;
- V = $0.696 in both regimes;
- VoT relaxed = 0.0000696 $/s;
- VoT urgent = 0.0011136 $/s.

They are derived by the rule in §8 (s = 1.392499 → 1.392). No other constant changes.

**0b-2. Step-0 reserve audit (before the freeze).**
- Run `analysis/exp0b/reserve_headroom.py` on `results/pilot` and apply the decision rule in §2.
- If it passes, the reserve carries forward unchanged.
- If it fails, a separate, documented infrastructure decision is made before the freeze, and `study.py` is rerun to
  confirm 0b-1.

**0b-3. Freeze (SPEC §7.4, header, §12 and validity (i)).**
- Run `freeze --pilot results/pilot` from the 0b-1 constants, with the unchanged procedure.
- Write the result to `data/exp0b/frozen.json`; that path replaces `data/frozen.json` wherever SPEC §7.4, the header,
  §12 and validity condition (i) name it.
- Commit it, and record its sha in EXPERIMENT_STATUS.
- The expected outcome is repair steps (0, 0, 0) and R = 3. Any other outcome is reported as is and is not tuned.

**0b-4. Artefacts.** 0b results go to `results/exp0b/…`. Experiment 0's artefacts are never overwritten.

**0b-5. Record (EXPERIMENT_STATUS and SPEC_0B §11).** *Experiment 0: calibration failure after live pilot; no
developmental-policy hypothesis test performed.* Also: 0b-0 to 0b-4, their rationale, and a pointer to this proposal.

**Implementation, not done here.**
- The code needs a way to select the 0b constants and `data/exp0b/frozen.json` in `freeze`, `run` and `report`; the
  0b-0 fix; and tests that the 0b constants load and verify and that Experiment 0's files are untouched.
- No runtime code changes, and no prompt template changes. Only the rendered numbers change.

**Main-run size at R = 3:** 15 × 2 × 4 × 3 = 360 runs. The oracle's best organizations spend $0.028–$0.196 of
list-price API money per run; live runs will cost more.

## 11. Risks and limitations

1. **Reserve headroom is unverified** (§2). At a median of about 0.50 tokens per character it rests on the 1,000-token
   allowance. Observation size is not bounded: duplicate targets, wide SQL and simultaneous reports can exceed 50,000
   characters. Violations would be retried as infrastructure errors and could threaten validity (iv). The audit gates
   the freeze, but it protects realistic observations, not pathological ones.
2. **Reusing a pilot run under Experiment 0 constants.** The rendered prompt numbers (V, VoT, balance) differ in 0b.
   The tokenizer ratio should be insensitive to that, while reasoning tokens could shift slightly. The perturbation grid
   (r ± 25%, reasoning × 0.5–2) and validity condition (v), the realized manipulation check, cover this.
3. **Criteria-check power is optimistic.** It assumes the pilot's `single` accuracy of 1.0. A less accurate
   developmental agent would make R = 3 (IDEAL 0.855) under-powered. The rule for choosing R is pre-registered and is
   not changed.
4. **Bootstrap reproducibility** until 0b-0 lands. Without it, R and the verdict's CIs depend on `PYTHONHASHSEED`.
5. **P labels are more robust than designed** (§6). That comes from pilot physics, not from a 0b choice. It makes the
   parallel urgent cells unambiguous, which helps any policy recognise them, and relaxes no criterion.
6. **Inherited design limits, not repaired by 0b:**
   - only 4 P cells, all parallel-urgent;
   - no I cells, so H2 is uninformative;
   - thin S margins;
   - a budget that does not bind the best organizations;
   - one-sided allocation exposure;
   - lifetimes that do not bind.
7. **Researcher degrees of freedom** in adding the currency family and the multiplier rule mid-analysis (§9).
8. **Units.** All 0b quantities are in list-price dollars. Relative to Experiment 0's design, V, B and VoT are 1.392×
   larger; equivalently, one "design dollar" equals $1.392 of list-price spend. 0b fitness values and Experiment 0
   dollar thresholds are not directly comparable.
9. **An unobserved regime.** 0b tests the question in the same designed environment at its intended economics. It
   says nothing about environments where money scarcity binds the topology.

## 12. Statement on live data

No live developmental or router output was produced or used, at any point. The only live data behind this proposal
are the Experiment 0 pilot's summary statistics as you reported them: `single` and `central` on held-out pilot tasks
X1–X3. No pilot event log was read, because the logs are not in this environment. Every other number was produced by
the LLM-free calibration oracle with the scripts in `analysis/exp0b/`. No Anthropic API call was made.
