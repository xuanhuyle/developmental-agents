# Experiment 0c: decision memo

**Status: decision memo only.**
- Nothing here is implemented, no API was called, and no live run was made.
- Experiment 0b is unchanged, and remains permanently recorded as **UNINFORMATIVE because the preregistered realized
  manipulation check failed**.
- Any successor needs its own pre-registration, committed before any of its live output exists. SPEC.md's header
  forbids weakening §§7–9 after main-suite results exist, so 0b cannot be amended.

## Evidence

| tag | source |
|---|---|
| **[live]** | the experimenter's run of `analysis/exp0b_diagnostic/traces.py` on the 0b main-run and pilot logs (the logs are not in the repository) |
| **[code]** | the repository at 44da120 |
| **[sim]** | the LLM-free `analysis/exp0b_diagnostic/offline.py` in the real runtime modes, at frozen 0b constants |

**[live] facts:**
- 360/360 runs completed, and the evaluator and an independent recomputation agree.
- Validity (v) failed: on B-urgent, `central` scored 0.2830 against 0.3552 for `single`.
- `central` used exactly one child in every main-run and every pilot run. In the P cells that one child read all 6 or 8
  documents.
- `developmental` and `router` made zero SPAWN attempts across all 90 runs each, and no SPAWN was rejected.
  - In the P cells the root makes one QUERY naming every document ("Read all six region reports in one query.").
- Pilot task X2 urgent: `single` ≈ 0.334, `central` ≈ 0.241.
- Main-run token statistics: 988 LLM calls, r = 2.0277, median reasoning 45 tokens. The frozen values are 2.0052 and 36,
  so both lie inside the calibration grid's range.

## 1. Final diagnosis of 0b

| | finding | confidence |
|---|---|---|
| **A. Hard implementation defect** | **None found.** See the note below the table. | high |
| **B. Oracle/live baseline mismatch** | **Confirmed, and sufficient on its own for the failed (v).** See below. | high |
| **C. Semantic/action-interface problem** | **Not a defect; a possible contributor whose causal role cannot be identified.** See the one-QUERY affordance below. | low–medium (as a contributor) |
| **D. Substantive model-policy behaviour** | **Confirmed as a description, with no verdict weight.** See below. | high as a description; unknown as to cause |

**A.** Every `central` SPAWN succeeded, no SPAWN was ever rejected, and no code limits the number of children
(`runtime.py:452–457`). The live token statistics match the calibration, and the independent recomputation agrees with
the evaluator.

**B.**
- **What was specified.**
  - SPEC §6 lets the LLM choose `central`'s list of children.
  - §7.3 (the criteria check) assumes `central` = the best one-shot division.
  - (v) is computed from the live runs.
  - This inconsistency has been in SPEC since commit 2851d2d.
- **What live `central` did.** It chose one child in 100% of runs. One child cannot beat `single` [sim]:
  - at the live token statistics, 0.279 against 0.343 for `single`, with the calibrated fan-out at 0.548;
  - live `central` scored 0.2830.

**D.**
- **Never divided.** Neither `developmental` nor `router` divided. For `developmental`, zero spawns in 90 runs gives a
  one-sided 95% upper bound of 0.033 on the per-run spawn probability, and zero parallel runs in the 12 P-cell runs
  gives 0.221.
- **Could emit SPAWN.** The model can produce the action, since forced `central` did so every time. Forced to divide,
  it delegated rather than parallelized.
- **Not a verdict.** Because (v) failed, this observation is not a test of H.

**The one-QUERY affordance.** QUERY takes up to 10 requests, and within one agent the sources are processed one after
another: elapsed time adds up (`runtime.py` sums the per-source latencies). Different agents process concurrently.
- **Is it a bug?** No. The prompt says so explicitly: "They are processed one after another" and "Different agents act
  concurrently". SPEC §10 declares single-agent parallel tool calls out of scope. The one-QUERY plan is also the
  oracle's *optimal solo plan*, and live `single` performs at the oracle-solo level.
- **What is uneven is salience, not truth.** One QUERY makes the solo plan two decisions against 8–10 for a division,
  and the prompt foregrounds per-decision cost ("The decision itself costs money and simulated time"; "Your entire
  conversation so far is re-read, and paid for, on every step"). The time cost that outweighs this is left to arithmetic
  from the catalog: about 336–351 s, or about 0.54–0.56 of the score under `urgent`. That document processing overlaps
  across agents is stated only generically.
- **What the evidence shows.** The pattern — a batch read in developmental and router, and one child reading the whole
  batch in forced `central` — fits a model that treats a multi-source QUERY as one unit of work and does not see agent
  concurrency as a way to save time. It also fits a model that never weighed time at all.
- **What 0b cannot tell apart.** One-sentence rationales at a median of 45 reasoning tokens cannot distinguish those
  two, and a missing mention of time is weak evidence. The affordance never varied in 0b, so its causal role is
  **unidentified**.
- **Conclusion.** It is a plausible salience hazard: one action *looks like* batching even though elapsed time is
  additive. It is not a misleading statement and not a defect.

## 2. What 0b established, and what it did not

**It established:**
1. The failed (v), and hence UNINFORMATIVE, is explained by the realized one-child `central` topology. The cause is a
   specification inconsistency, not a runtime defect.
2. **Descriptively** (no confirmatory weight): at effort `low` with the frozen prompt, the frozen model never attempted
   SPAWN as `developmental` or `router`, including in the P cells, where the calibrated division beats solo by about 0.2
   fitness [sim]. Forced to divide, it chose one child every time.
3. The solo physics behaved as calibrated: live `single` ≈ oracle solo, and the token statistics are within the grid's
   range.
4. The pilot already carried the warning, but the protocol had no check of realized organizations.
5. The synthetic criteria check established the evaluator's power and specificity only under idealized baselines.

**It did not establish:**

| claim | status |
|---|---|
| "The current low-effort policy fails to discover division" | Narrowly, as description only: *it did not divide* under this model, effort, prompt and task set. "Fails to discover" implies a search we cannot see. |
| "Adaptive architecture has no value" | **No.** In simulation division is worth about +0.2 in the P cells. It is untested live, because **no live run in the pilot or in 0b had ≥ 2 children**. |
| "The lifecycle mechanism is wrong" | **No.** `developmental` never spawned, so its SPAWN, WAIT, allocation, lifetime and termination decisions were never exercised. |
| "The prompt representation is insufficient" | **Not attributable.** Representation, effort and model are confounded, and none was varied. We can say only that *this* combination did not elicit division. |
| "The `central` baseline was invalidly operationalized" | **Yes, narrowly.** It was operationalized inconsistently with the calibration and the manipulation check that assume it. An LLM-chosen central is a legitimate baseline for some question, but not for (v) as written. |
| H falsified or NOT SUPPORTED; why the policy did not divide; any generalization; anything about information-dependent restructuring | **No.** |

## 3. Should the developmental treatment remain unchanged?

**Path A: clean replication with a scripted `central`.**
- **Is it valid?** Yes, on the decisive stratum:
  - with `central` fixed by construction, the urgent part of (v) tests whether the designed trade-off materializes
    with live agents;
  - criterion 2 tests the treatment.
- **Expected result.** Criterion 2 fires. The probability that it does not is ≤ 0.031 at 0b's pessimistic P-cell
  bound, and about 0 at the all-runs bound. The pre-registration must say so.
- **Is it still the right next test? Yes, but only small** (§6):
  - its one change is fixed by text written before 0b (§7.3), so it cannot be tuning;
  - it validates the instrument every successor needs, which is genuinely uncertain because live multi-child division
    was never observed in the pilot or 0b;
  - it gives the original H its only valid test.
- **The honest objection.** Its treatment outcome is almost known, so its developmental arm buys procedural closure,
  not much new knowledge.

**Path B: new representation.** Each option, classified:

| option | classification | tuning risk |
|---|---|---|
| state that source processing by different agents overlaps in time | a clarification of a rule stated only generically, but chosen *because* of 0b → **new hypothesis** | lowest of the set |
| show the estimated elapsed time of an N-source QUERY (or per-document seconds) | a derived restatement, but scaffolding in effect, because it makes the key consequence salient → **new hypothesis** (legibility) | moderate |
| expose predicted cost and time of candidate actions or organizations | **policy scaffolding**. It borders on suggesting an organization, against the pre-registered rule that the prompt "never suggests an organization", and tests choice from a menu. | high |
| raise reasoning effort | **treatment change** (deliberation) → new hypothesis. It also changes the economics, since reasoning tokens are priced and the grid covers 18–72, so a recalibration is needed. | moderate–high |
| decouple QUERY batching from concurrency | **environment change**. Capping QUERY at one source makes solo costlier and widens P margins, which makes it the most tuning-prone. Making a batch concurrent removes the P-cell trade-off, which SPEC §10 puts out of scope. | high |

Only a factual error in what the agent is told would count as pure instrumentation clarification, and none was found.

**Would using these after 0b be tuning?** Yes, if presented as a repair or a replication, or if iterated.

**Honest framing** is a separately pre-registered hypothesis, for example: "when the time consequences of actions are
legible, without any suggested organization, the frozen model's organization tracks the value of time." It requires:
- exactly one variant text, fixed in advance;
- a concurrent arm with the treatment unchanged;
- a live-validated manipulation (a scripted `central`);
- the relaxed twins, to detect always-spawn collapse;
- 0b and 0c declared as its motivation, never pooled with it, and never reported as support for H.

A positive result would show that the model divides when the consequences are made legible, not that it derives
division unaided.

**Decision: the treatment stays unchanged in the next step.** A changed representation is a later, separate decision
(§9).

## 4. `central` baseline redesign

**The smallest defensible definition (scripted `central`).**
- **What code generates.** The root's first action is generated by code, not the LLM: a SPAWN with forced wait.
- **Children and partition.**
  - k = that cell's `router_div` fan-out in `data/exp0b/frozen.json`: 3 for T01 and T07, 4 for T04 and T10.
  - Documents are split round-robin over the route's document ids in frozen order (`docs[i::k]`).
- **Objective template**, fixed and with empty context: "Find the facts needed for: <question> Read only the sources
  named in this objective: <ids>".
- **Unchanged.**
  - Allocation and lifetime use the existing fixed rule (an equal share of 50% of the balance after fees; 60% of the
    remaining time).
  - Every later root step and every child is a live LLM call, with the unchanged prompts, schema, MODE RULES line
    (still true as written), constants, model and effort.
- **The scripted step is charged as a decision.**
  - It is priced as the calibration prices oracle steps, at the **frozen** assumptions (r 2.0052, 36 reasoning
    tokens), pre-declared so that there is no fork. That includes its latency.
  - It is written into the root's transcript with a fixed neutral rationale, so later steps re-read it and pay for it.
  - Otherwise `central` would get a free decision.

**How it fares:**
- **Matches Baseline B's intent?** Yes, and more literally than the LLM version: SPEC §6 calls it a "fixed
  decomposition, decided before any look at the data".
- **Matches the criteria check?** Yes, exactly: in these cells `central` = `router_div`.
- **Unfair future information?**
  - No. k and the partition come from a file frozen *before any 0b main-run output existed*.
  - The documents are identifiable at t0 from the question and the catalog ("Across the six regions …").
- **Equal resources?** Yes: the same budget, deadline, value of time, prices, caps, catalog and audit record, and the
  same allocation rule.
- **Strength.** It is deliberately the strongest fixed decomposition, the designer's best k. That is appropriate for
  (v). It must not be read as a contest between two LLM policies.

**What the topology may use:**
- the question;
- the catalog;
- the regime (the brief shows it);
- design constants frozen before any live output: k, the route and the partition rule from `frozen.json`, and the
  template.

**What it may not use:** SQL strings, SQL results (such as which candidates qualify), document contents, answers, or
anything observed in any live run.

**Leak warning for any full benchmark [code].** Copying the oracle's objective text (`calibrate._spawn`) would leak
information in **16 of 30 cells**:
- in T03, T09 and T15 (`atstart`), the objectives name only the qualifying candidates, which is post-SQL information,
  plus the exact SQL;
- in T05, T06, T11, T13 and T14, they carry the exact SQL.

Those cells need a template that uses only t0 information, followed by an offline recalibration, before any freeze. The
4 P cells are leak-free.

**Implementation constraints, to settle in the pre-registration (not implemented here):**
- Audit parity (iii) requires one policy configuration across modes, so the scripted step must be mode-dependent
  behaviour of the same policy.
- The existing report pipeline would mark a P-only stage UNINFORMATIVE by construction, so the stage needs its own
  small pre-registered analysis, tested on synthetic records.
- "Read only" is an instruction, not an enforced permission, so realized organizations must be logged and checked.

## 5. Router in the next narrow test

**Exclude it from Stage 1, and declare the deviation.** `router` never enters criteria 1–5 or (v). It enters only H2,
which "never changes the §8 verdict", and the calibration found no I cells.

In a full benchmark, `router` runs *can* make a verdict UNINFORMATIVE through audit parity (iii) and completion (iv),
but they cannot flip supported versus not supported. No Stage 1 decision depends on them.

**Is removing it after observing results acceptable?** The exclusion rests on facts that were pre-registered before 0b
ran (H2 only, I = 0), not on 0b's router result. Any later full benchmark restores `router` exactly as pre-registered.

For the information-dependent experiment, the one-shot comparator should itself be scripted and use only t0
information, for the same reason as `central`: a live router that never spawns is a degenerate comparator.

## 6. Staged design

**Stage 0: offline, no API calls.** Before any live call:
- scripted `central` reproduces the per-cell offline fitness of the frozen organizations to within ±0.005;
- the prompt fingerprint (53790f89…) and audit parity hold;
- the objectives contain only document ids identifiable at t0;
- a fake-client dry run of all 36 runs completes;
- the Stage 1 analysis passes on synthetic records;
- the pre-registration is committed and its SHA recorded.

**Stage 1: live.**

| design | value |
|---|---|
| cells | the 4 P cells: T01, T04, T07 and T10, urgent (= P = P_urgent = B-urgent) |
| modes | `single`, scripted `central`, unchanged `developmental` |
| repeats | R = 3, in seeded shuffled blocks |
| runs | **36** |
| LLM calls | ≈ 144: 24 `single`, 96 `central` (children × 2 plus one live root step), 24 `developmental`. Up to ≈ 190 with extra steps, i.e. ≈ 15–19% of 0b's 988. |

**Why R = 3.** It is the pre-registered R, and it reproduces criterion 2's statistic exactly.
- Criterion 2 does not fire iff at least 6 of 12 P-cell runs are parallel.
- The urgent part of (v) then tolerates two more wrong `central` answers than `single` (margin +0.205 [sim]; a wrong
  answer costs 1.0 in that run, i.e. 0.083 of the mean).
- Assuming `single` is correct, (v) passes with probability ≈ 0.98, 0.89 and 0.56 at a 5%, 10% and 20% `central` error
  rate.
- R = 2 is the floor for (v) alone, and R = 5 buys little.

**Is staging valid?** Yes, as a pre-declared, binding **futility-only** gate:
- Criterion 2 depends only on these 12 `developmental` runs, and it is necessary for SUPPORTED. So stopping on it
  cannot inflate a later false SUPPORTED.
- Its stopping probabilities are the criterion's own operating characteristic, not added error: 0.387 at a true rate
  of 0.5, 0.158 at 0.6, 0.039 at 0.7, 0.004 at 0.8, and ≈ 0 for an ideal policy.
- Stage 1 data are **never pooled** into a later verdict, and 0b data never enter any gate. A combined 0b + 0c figure
  may be reported descriptively only.

**What Stage 1 can conclude:**
- whether live agents realize the designed urgent trade-off when division is enforced (its size, and a cost/quality
  decomposition);
- whether realized organizations match the calibration;
- whether the unchanged treatment divides where division demonstrably pays;
- whether H can still be supported by this design.

**What it cannot conclude:**
- a full §8 verdict, because the relaxed and A parts of (v) and criteria 1, 3, 4 and 5 are not evaluated;
- causes;
- generality beyond 4 cells, 2 task templates, one model and effort `low`;
- H2;
- anything about information-dependent restructuring.

## 7. Stop conditions (pre-declared, evaluated in order)

1. **Completeness.** Fewer than 2 completed runs in any cell × mode, or under 90% per mode after the standard
   infrastructure retries → **UNINFORMATIVE**. No redesign.
2. **Instrument integrity.** Every scripted-`central` run must create k children with overlapping QUERY processing. If
   2 or more of 12 do not → **UNINFORMATIVE**.
   - This check is needed because the mean alone would pass even if about 76% of runs degraded to one-child fitness.
3. **Manipulation (strict, as pre-registered).** Validity requires all of the following:
   - mean fitness of scripted `central` > mean fitness of `single` over the 12 + 12 runs;
   - `single` accuracy ≥ 0.75 on these cells;
   - audit parity holds;
   - `single` hits a cap in ≤ 5% of runs.

   If the manipulation fails → **STOP.** The designed trade-off is not realized with live agents. There is no Stage 2,
   and neither D nor E on this environment without a redesign, which would be a new pre-registration. Report the
   cost/quality decomposition.
4. **Futility.** If the stage is valid and `developmental` is parallel in **≤ 5 of 12** P runs (criterion 2 fires) →
   **STOP.**
   - The pre-declared label: "Under a live-validated urgent manipulation, criterion 2 fires. H is not supported for
     the frozen treatment on the decisive P stratum. The full §8 verdict was not evaluated." Never "H refuted".
   - The same conclusion follows for zero SPAWN attempts, which is the expected outcome.
   - No full benchmark.
5. **GO.** If the stage is valid and `developmental` is parallel in **≥ 6 of 12**:
   - first audit for treatment drift, since the result would contradict 0b;
   - then write a fresh full pre-registration: all 30 cells, all 4 modes, a leak-free t0-only `central` template
     recalibrated offline, R from a rerun criteria check, and no pooling.

**Research-direction stop rules:**
- **If (3) fails.** Reconsider the mechanism-level assumption that live children can read, report and be aggregated at
  the calibrated cost before building anything on this environment.
- **If (4) fires.** The primitive-decision line under the neutral representation is closed. At most **one** further,
  separately pre-registered representation experiment (E, §3) may follow. If it too fails criterion 2 under a
  live-validated manipulation, abandon LLM-emergent division with this model class and effort, and do not proceed to
  the information-dependent experiment with LLM lifecycle policies.
- **Never** iterate prompt variants on these 4 cells.

## 8. Relation to the stronger research question

The eventual question is whether architecture can change usefully in response to information unavailable at t0.
Experiments 0 and 0b do not test it:
- the calibration found no I cells;
- the recommended extension in SPEC §10 and EXPERIMENT_STATUS.md needs new cells in which mid-task information changes
  the optimal organization.

**Moving to it now would be premature:**
- A policy that never divides where division pays from t0 is very likely to hit a floor in cells that require dividing
  after new information.
- Its result would be uninterpretable without a live-validated division instrument and a scripted one-shot
  comparator.

**Another full benchmark on the primitive spawn decision is not worthwhile:**
- Criterion 2 rests only on the 4 P cells.
- The treatment's outcome there is nearly certain.
- The other 26 cells cannot rescue SUPPORTED once criterion 2 fires.

**Worth doing:**
- the 36-run Stage 1, because its manipulation check validates an instrument the stronger experiment also needs;
- offline, zero-API design and calibration of I cells, which can proceed independently.

## 9. Recommendation

**B. Run a small clean replication with a scripted `central` and an unchanged `developmental`** (Stage 1 above, 36
runs).

**Why:**
- **It is the smallest step that turns an invalid observation into a valid, pre-registered test.** It makes exactly
  one change, and that change was fixed by text written before 0b.
- **It resolves the one genuinely open empirical question** every successor depends on: whether live agents realize
  the designed parallel trade-off. No pilot or 0b run ever divided across two or more children.
- **It closes the original H honestly and cheaply.** It pre-declares that the expected outcome is a futility stop.
- **The alternatives are weaker:**
  - C is dominated.
  - D would hit a floor.
  - A would leave the hypothesis without any valid test and the environment unvalidated, to save about 150 calls.
- **E is the strongest alternative.** It has higher information value, but its instrument is the one B validates, and
  its representation wording is a degree of freedom chosen after the failure. It should be decided after B, as a
  separate pre-registration.

**The next decision after B is A or E, not C.**

**Exact go/no-go for Stage 2:**

> GO iff Stage 1 is valid under §7 (1)–(3): completeness, AND at most one completed scripted-`central` run fails to
> realize the frozen k-way parallel division, AND mean fitness(scripted `central`) > mean fitness(`single`) over the 12 + 12 B-urgent runs
> (with `single` accuracy ≥ 0.75, audit parity, and ≤ 5% `single` cap hits), AND unchanged `developmental` is parallel
> in ≥ 6 of 12 P-cell runs (criterion 2's statistic parallel_rate(P) ≥ 0.50; with missing runs, computed as that
> statistic).
>
> Otherwise, NO-GO, with the pre-declared conclusion of §7.

## Limitations

- **The live facts are as reported** by the experimenter's trace run. The logs are not in the repository.
- **The Stage 1 probabilities assume** independent runs and simulator-accurate costs. The 12 runs are clustered in 4
  tasks from 2 templates, so the effective sample size is smaller.
- **The oracle assumes perfect aggregation of child reports**, so the live (v) check is exactly where the calibration
  is least tested.
- **This memo decides nothing irreversible.** Stage 1 still requires its own pre-registration, the Stage 0 checks, and
  a separate approval before any API call.
