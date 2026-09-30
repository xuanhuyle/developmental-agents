# Experiment 0c: decision memo

**Status: decision memo only.** Nothing here is implemented, no API was called, and no live run was made.

- **The 0b verdict is unchanged.** Experiment 0b remains permanently **UNINFORMATIVE because the preregistered realized
  manipulation check failed** (EXPERIMENT_0B_DIAGNOSTIC.md).
- **The status log is incomplete.** EXPERIMENT_STATUS.md, which is append-only (SPEC §12), does not yet record the 0b
  main run or its verdict. That entry is a precondition for any successor.
- **0b cannot be amended.** SPEC_0B.md's header forbids weakening §§7–9 after any 0b main-suite result exists. Any
  successor is a new pre-registration, committed before any of its live output exists.

## Decision summary

1. **What 0b established.**
   - The failed (v) is fully accounted for by live `central` choosing one child in every run. The specification let the
     LLM choose that topology, while the calibration and (v) assumed the best one-shot division; the LLM chose one
     child. No code defect was found.
   - Descriptively, and with no verdict weight: the treatment never attempted SPAWN.
2. **Is the one-QUERY affordance materially misleading?**
   - **As a description, no.** The prompt states that sources are processed "one after another", and it is not a bug.
   - **As salience, it may matter.** It makes the solo plan the cheapest-looking plan to write, while its time cost is
     left to arithmetic.
   - Whether it *materially* caused non-division is **unidentified**.
3. **Should the unchanged `developmental` be tested again?**
   - **Yes, once, and only as the 12-run arm of a small Stage 1.** A test of criterion 2 needs a sample concurrent with
     a validated manipulation, and 0b's data cannot be reinterpreted.
   - The expected outcome (criterion 2 fires) is declared in advance.
4. **Is another 360-run benchmark justified?** **No, not now.** Only after a Stage 1 GO, which is unlikely.
5. **Recommended next experiment: option B.** A small clean replication with a scripted `central` and an unchanged
   `developmental`.
6. **Size:**
   - 4 runs of a held-out instrument pilot, plus **36 Stage-1 runs**: 40 in all;
   - ≈ 160–210 LLM calls, about 16–21% of 0b's 988.
7. **Go/no-go:** see §9.

**Labels.**
- In §1, A–D are the brief's diagnosis categories. The diagnostic's C ("substantive, qualified") is D here, and C here
  is the interface question.
- The options in §§7–9 are:
  - **A:** stop;
  - **B:** Stage 1 of this memo;
  - **C:** a new full benchmark;
  - **D:** the information-dependent experiment;
  - **E:** one pre-registered representation experiment.
- "Path A" and "Path B" in §3 are options B and E.

**Evidence.**
- **[live]** means the experimenter's run of `analysis/exp0b_diagnostic/traces.py` on the local 0b and pilot logs.
  Those logs are not in this repository.
- **[code]** means the repository at 704fe5f.
- **[sim]** means the LLM-free `offline.py` in the real runtime modes, at frozen 0b constants and the live token
  statistics (r 2.0277, 45 reasoning tokens) unless marked "frozen" (r 2.0052, 36).

**[live] facts:**
- **Run and verdict.** 360/360 runs completed, and the evaluator and an independent recomputation agree. Validity (v)
  failed: on B-urgent, `central` scored 0.2830 against 0.3552 for `single`.
- **`central`.** It used one child in every main-run and pilot run. In the P cells that child read all 6 or 8
  documents.
- **`developmental` and `router`.** Zero SPAWN attempts across 90 runs each, none rejected. In the P cells the root
  makes one QUERY naming every document ("Read all six region reports in one query.").
- **Pilot X2 urgent.** `single` ≈ 0.334, `central` ≈ 0.241.
- **Token statistics.** 988 LLM calls; r 2.0277 and a median of 45 reasoning tokens, both inside the calibration grid's
  range.
- **Closed flag.** With zero spawns, the twin and dissociation contrasts are exactly 0, so the diagnostic's §2
  consistency flag is closed.
- **Not reported.** The rationale-keyword census from `traces.py` was not among the reported facts. The diagnostic's
  pre-declared reading of it (§8) therefore cannot yet be applied, and this memo does not substitute its own.

## 1. Final diagnosis of 0b

| | finding | confidence |
|---|---|---|
| **A. Hard implementation defect** | None found. See below. | high |
| **B. Oracle/live baseline mismatch** | **Confirmed, and sufficient for the failed (v).** See below. | high |
| **C. Semantic/action-interface problem** | **Not a defect; a possible contributor whose causal role cannot be identified.** See the one-QUERY affordance below. | low–medium (as contributor) |
| **D. Substantive model-policy behaviour** | **Confirmed descriptively, with no verdict weight.** See below. | high as description; cause unknown |

**A.** No SPAWN was rejected, and the recomputation agrees with the evaluator. No code reduces the number of children
the LLM lists: the runtime creates exactly `len(children)` agents (`runtime.py:452`). The caps (1–8 children at the
root, 9 live agents; `runtime.py:396, 455–458`) never bind for a one-child SPAWN.

**B.**
- **The specification.** SPEC §6 lets the LLM choose `central`'s list of children. §7.3 and the synthetic criteria
  check assume the best one-shot division, and (v) uses the live runs. This has been so since 2851d2d.
- **The live runs.** Live `central` chose one child every time, and one child cannot beat `single` [sim]: 0.279
  against 0.343, while the calibrated fan-out scores 0.548. Live `central` scored 0.2830.

**D.**
- **Never divided.** `developmental` and `router` never divided. If runs were independent with a common rate, the
  one-sided 95% upper bounds would be 0.033 per run (0 in 90) and 0.221 for P-cell parallelism (0 in 12).
- **Could emit SPAWN.** The model can emit SPAWN: forced `central` did so every time, but delegated rather than
  parallelized.
- **Not a test of H.** Because (v) failed, none of this tests H.

**The one-QUERY affordance.**
- **The semantics.** A QUERY takes up to 10 sources. Within one agent they are processed sequentially, and elapsed time
  is additive; agents run concurrently.
- **Accurate, not a bug.** The prompt says both. SPEC §10 declares single-agent parallel calls out of scope. The
  one-QUERY plan is the oracle's *optimal solo plan*, and live `single` performs at oracle-solo level.
- **Uneven salience.**
  - The solo plan is two LLM calls in all, against 8–10 system-wide for a division.
  - The prompt foregrounds per-decision cost.
  - The time cost that outweighs this must be computed from the catalog: about 336–343 s of document processing,
    about 0.54–0.55 of the score under `urgent`.
  - That document processing overlaps across agents is said only generically.
- **What the pattern fits, and what it cannot tell.** The pattern — batch reads, and forced `central` handing the whole
  batch to one child — fits a model that treats one QUERY as one unit of work. It equally fits a model that never
  weighed time. One-sentence rationales cannot tell these apart, and the affordance never varied.
- **Verdict.** A plausible salience hazard: one action *looks like* batching while time adds up. It is not a defect,
  and its causal role is unidentified.

## 2. What 0b established, and what it did not

**It established** the explanation of the failed (v) (§1 B), the descriptive behaviour in §1 D, that the solo
physics behaved as calibrated (live `single` ≈ oracle solo), and that the pilot already carried the warning: no step
inspected realized organizations.

| question | answer |
|---|---|
| The current low-effort policy "fails to discover division"? | Only as description: *it did not divide* under this model, effort, prompt and task set. "Discover" implies a search we cannot see. |
| Adaptive architecture has no value? | **No.** 0b never exercised an adaptive organization. By design [sim], division beats solo by ≈ 0.2 in the P cells, with no designed edge over a one-shot router (I = 0). None of this was tested live: **no pilot or 0b run had ≥ 2 children.** |
| The lifecycle mechanism is wrong? | **No.** `developmental`'s SPAWN, WAIT, allocation, lifetime and termination decisions were never exercised. |
| The prompt representation is insufficient? | **Not attributable.** Representation, effort and model are confounded, and none was varied. |
| The `central` baseline was invalidly operationalized? | **Yes, narrowly.** It was inconsistent with the calibration and the check that assumed it. SPEC §6 is itself ambiguous: it says "1–K children" but calls the organization a "fixed decomposition". |
| H falsified; why the policy did not divide; generalization; information-dependent restructuring? | **No.** |

## 3. Should the developmental treatment remain unchanged?

**Path A (= option B): scripted `central`, everything else unchanged.**
- **Valid for criterion 2, a necessary condition for H.** The urgent part of (v) then tests whether live agents realize
  the designed trade-off, and criterion 2 tests the treatment. It cannot yield SUPPORTED or a full §8 verdict.
- **Not neutral.** The baseline change was chosen *after* (v) failed, and it makes that check pass by construction in
  simulation.
- **What limits the tuning.** Everything about it is fixed by artefacts committed before any 0b main-run output (§4),
  and it cannot make H easier to support: the treatment is unchanged, and the expected outcome is a futility stop.
- **Expected result: criterion 2 fires.**
  - With independent runs, P(it does not fire) ≤ 0.031 at 0b's P-cell bound.
  - The runs are clustered in 4 cells from 2 templates. If behaviour were fixed per cell, 0 of 4 P cells bounds it
    only at ≤ 0.73.
  - The expectation therefore rests on the uniformity of 0b's behaviour, not on the i.i.d. figure.
- **Still the right next test, if small.** It checks, for about 150 calls, the instrument any successor on these cells
  needs, and it gives criterion 2 its first valid test.

**Path B (= option E): a changed representation.**

| option | classification |
|---|---|
| state that source processing by different agents overlaps in time | a clarification of a generically stated rule, but chosen *because* of 0b → **new hypothesis** (lowest tuning risk) |
| show the estimated elapsed time of an N-source QUERY | restates a derivable quantity, but acts as scaffolding by making the key consequence salient → **new hypothesis** |
| expose the predicted cost and time of candidate actions | **policy scaffolding**. It borders on suggesting an organization, against the design rule that the prompt "never suggests an organization" (`prompts.py:3–5`). |
| raise reasoning effort | **treatment change** → new hypothesis. It is part of the audit record, so it applies to every mode, and it moves reasoning tokens outside the calibrated 18–72 range → recalibration. |
| decouple QUERY batching from concurrency | **environment change**. One source per QUERY makes solo costlier, which is the most tuning-prone option. Concurrent batches remove the P-cell trade-off, which SPEC §10 puts out of scope. |

No factual error was found in what the agent is told, so none of these is a pure instrumentation fix. Using any of them
after 0b is tuning if it is presented as a repair or iterated.

**Honest framing** is a separately pre-registered hypothesis ("when the time consequences are legible, without a
suggested organization, the frozen model's organization tracks the value of time"). It requires:
- one variant text, fixed in advance;
- a concurrent arm with the treatment unchanged;
- a scripted-`central` manipulation check;
- the relaxed twins and the dissociation cells (T06, T13, T14 urgent), to detect always-spawn and surface-cue
  spawning;
- no pooling with 0b or 0c, and never reporting it as support for H.

A positive result would show that the model divides when the consequences are legible, not that it derives division
unaided. **The treatment therefore stays unchanged in the next step.**

## 4. `central` baseline redesign

**Scripted `central`: what code generates.**
- **The first action.** The root's first action is generated by code as a SPAWN with forced wait.
- **Children and partition.**
  - k and the route come from the cell's `router_div` in `data/exp0b/frozen.json` (sha 0d10865d…): `fanout3@r0` for
    T01 and T07, `fanout4@r0` for T04 and T10.
  - The documents are split round-robin (`docs[i::k]`, `calibrate.py:98`) in the route's order in
    `devagents/environment/tasks.py`.
- **Objective template.** The oracle's template (`calibrate.py:108`): "Find the facts needed for: <question> Read only
  the sources named in this objective: <ids>", with empty context.
- **Rationale.** The oracle's exact text, "Split the work across agents."
- **Allocation.** The existing fixed rule: an equal share of 50% of the balance after fees, and 60% of the remaining
  time.
- **The scripted step is charged as a decision.**
  - It is priced as the calibration prices oracle steps, at the **frozen** assumptions, pre-declared.
  - That is marginally cheaper than a live step, by well under 0.01 fitness.
  - The step is written into the root's transcript, so later steps re-read it and pay for it.
- **Unchanged.** Everything else is live and unchanged: the later root steps, the children, the prompts (the MODE RULES
  line stays true), the model and the effort.

**Checks:**
- **Baseline B's intent.** It adopts §7.3's reading of the ambiguous §6: "fixed decomposition, decided before any look
  at the data". That reading was chosen after (v) failed.
- **The synthetic criteria check.** It matches exactly: `central` = `router_div`.
- **Future information.** None. Every input was committed before any 0b main-run output. The documents are
  identifiable at t0 from the question and the catalog.
- **Equal resources.** Yes: the same budget, deadline, value of time, prices, caps and catalog, and the same allocation
  rule.
- **Strength.** It is deliberately the strongest fixed decomposition. It is not a contest between two LLMs.

**What the topology may use:**
- the question;
- the catalog;
- the value of time that the brief shows;
- the constants above.

**What it may not use:** SQL strings, SQL results (for example which candidates qualify), document contents, answers,
or anything observed in a live run.

**For any full benchmark.** Copying the oracle's objectives leaks SQL strings or post-SQL candidate lists in 16 of 30
cells: T03, T09 and T15 (`atstart`), and T05, T06, T11, T13 and T14. Those cells need a template that uses only t0
information, and an offline recalibration. The P cells are leak-free.

**Audit parity.** The scripted first step is a declared asymmetry.
- Record it in the policy configuration (for example `central_first_step: "scripted"`).
- Evaluate parity (iii) on every other field. Do not hide it inside a shared policy class.

## 5. Router in the next narrow test

**Exclude it from Stage 1, and declare the deviation.**
- **Its role.** `router` enters neither criteria 1–5 nor (v), only H2, which "never changes the §8 verdict", and the
  calibration found no I cells.
- **In a full benchmark.** Its runs can make a verdict UNINFORMATIVE through parity (iii) and completion (iv), but
  cannot flip it.
- **Timing.** These grounds were pre-registered before 0b. The decision is nevertheless taken after router's result
  was seen, and it is declared as such.
- **Restoration.** A full benchmark restores `router` exactly as pre-registered.
- **Scripting it** for a later experiment would change H2's meaning, and would be a new hypothesis.

## 6. Staged design

**Stage 0: offline, no API.**
- The scripted `central` reproduces offline per-cell fitness to within ±0.005.
- `verify_frozen` passes.
- The prompt fingerprint is 53790f89…, and parity holds on every field except the declared one.
- The objectives contain only document ids identifiable at t0.
- A fake-client dry run of every planned run completes.
- A dedicated Stage 1 analysis passes on synthetic records. The existing report would mark a P-only stage UNINFORMATIVE
  by construction.

**Stage 0-pilot: live, held-out.**
- **The runs.** Pilot task X2, urgent, `single` and scripted `central`, R = 2: **4 runs**, ≈ 18 calls.
- **The fan-out.** k = 3, X2's best fan-out at 0b constants [sim, frozen]: 0.557, against 0.355 for `single` and 0.291
  for one child.
- **Purpose.** It implements the diagnostic's §12 change: verify realized organizations before freezing.
- **Gate.** Stage 1 is committed only if every pilot `central` run creates its k children and each child reads its
  assigned documents.
- **Revisions allowed.** Implementation bugs and the template's wording may be revised on X2 only, and only before
  Stage 1 is committed.

**Stage 1: live, confirmatory, fixed size.**

| | |
|---|---|
| cells | T01, T04, T07 and T10, urgent (= P = P_urgent = B-urgent) |
| modes | `single`, scripted `central`, unchanged `developmental` |
| repeats | R = 3, in seeded shuffled blocks |
| runs | **36** |
| LLM calls | ≈ 144: 24 + 96 + 24. `central` makes k children × 2 plus one live root step. Up to ≈ 190 with extra steps. |

**Why R = 3.**
- **It is the pre-registered R, and it reproduces criterion 2 exactly.** The criterion fires iff parallel_rate(P) <
  0.50, the mean of the per-cell parallel fractions (`analysis.py:116–117`). With all 12 runs complete, that means
  fewer than 6 of 12.
- **It tolerates two extra wrong `central` answers.** The urgent part of (v) survives two more wrong `central` answers
  than `single` (margin +0.205; each wrong answer costs 0.083 of the mean). If `single` is always right, P(pass) ≈ 0.98,
  0.89 and 0.56 at a 5%, 10% and 20% `central` error rate.

**Validity of staging.** It is a pre-declared, binding validity-and-futility gate.
- Criterion 2 is necessary for SUPPORTED, so stopping on it can never create a false SUPPORTED.
- Because Stage 1 is **never pooled** into a later verdict, a policy must pass criterion 2 twice. So the gate *adds*
  false-futility risk near the threshold:

| true parallel rate | P(pass) with one test | P(pass) with both stages |
|---|---|---|
| 0.5 | 0.61 | 0.38 |
| 0.6 | 0.84 | 0.71 |
| 0.7 | 0.96 | 0.92 |
| ideal policy | ≈ 1 | ≈ 1 |

- This cost is accepted because 0b makes a rate ≥ 0.5 unlikely.
- 0b data enter no gate.

**Stage 1 can conclude:**
- whether live agents realize the designed at-start fan-out trade-off in these 4 cells, with a cost/quality
  decomposition;
- whether the unchanged treatment divides where division demonstrably pays;
- whether H can still be supported by this design.

**It cannot conclude:**
- a §8 verdict (the relaxed and A parts of (v), and criteria 1 and 3–5, are unevaluated);
- causes, or generality beyond 4 cells, 2 templates, one model and effort `low`;
- H2;
- anything about division after mid-task information.

**Stage 2 (only on GO) = option C.** A fresh, separately pre-registered full benchmark: 30 cells and 4 modes, the
t0-only template, and R from a rerun criteria check (≈ 360 runs). No Stage 1 data are pooled.

## 7. Stop conditions (pre-declared, evaluated in order)

0. **Fixed size.**
   - The 4 + 36 planned runs are fixed. Nothing is added or topped up after any output, except SPEC §8's 3
     infrastructure retries.
   - k, the partition, the template and the rationale are never revised on T01, T04, T07 or T10.
1. **Completeness.** At least 2 completed runs per cell × mode, and at least 90% per mode. Otherwise **UNINFORMATIVE**.
   An identical repeat under the same pre-registration is allowed once.
2. **Identity and validity.** Any of the following makes the run **UNINFORMATIVE**, with no statement about the
   trade-off:
   - on any run, the logged model identifier, effort, structured flag, prompt fingerprint, frozen sha or policy
     configuration differs from 0b's (apart from the declared field);
   - `single` accuracy is below 0.75 (fewer than 9 of 12 correct);
   - any `single` cap hit (1 in 12 already exceeds 5%).
3. **Instrument integrity (runtime level).**
   - A scripted-`central` run is *intact* iff the scripted SPAWN is accepted, all k children are created with their
     assigned objectives, and no child is starved or stopped by a runtime cap.
   - If 2 or more completed runs are not intact → **UNINFORMATIVE (defect)**. Only the bug may be fixed, and then
     Stage 0 and the pre-registration are repeated.
   - What children actually read is *behaviour*: it stays in the sample and counts in (4). The number of runs in which
     every child read exactly its assignment is reported, because the mean alone would still pass with up to 9 of 12
     runs degraded to one-child fitness.
4. **Manipulation: the B-urgent part of SPEC §8 (v), threshold unchanged.**
   - If mean fitness(scripted `central`) ≤ mean fitness(`single`) over the completed B-urgent runs → **STOP.**
   - The label is decided by which component explains most of the shortfall: "live aggregation quality fails" (lower
     `central` accuracy), or "the designed time/money trade-off is not realized" (cost/time).
   - Either way there is no Stage 2, and no successor on these cells without a new pre-registration.
5. **Futility.** If the run is valid and parallel_rate(P) < 0.50 (≤ 5 of 12 when all complete; zero SPAWN attempts is
   the expected case) → **STOP.**
   - Label: "Under a live-validated B-urgent manipulation, criterion 2 (never-spawn collapse) fires for the frozen
     treatment. Under SPEC §8 this criterion alone would make H NOT SUPPORTED in a valid full run. The full validity
     set and §8 verdict were not evaluated." Never "H refuted".
6. **GO.** If the run is valid and parallel_rate(P) ≥ 0.50 → Stage 2 (option C).

**Research-direction rules:**
- **After (4).** Before anything is built on this environment, reconsider the mechanism assumption that live children
  can read and report, and be aggregated, at the calibrated cost.
- **After (5).** The primitive-decision line under the neutral representation is closed. At most **one** option-E
  experiment may follow, and its variant is the only prompt variant ever run on these cells.
  - If it also fails criterion 2 under a validated manipulation: abandon LLM-emergent division with this model at
    effort `low`, and do not run the information-dependent experiment with LLM lifecycle policies.
- **Not optimized for a positive answer.**
  - The treatment is unchanged, and the expected futility stop is declared.
  - `central` is the strongest fixed decomposition.
  - No arm, cell, R, threshold or prompt changes after any Stage 1 output.

## 8. Relation to the stronger research question

The eventual question is whether architecture can change usefully in response to information unavailable at t0.
Experiments 0 and 0b do not test it:
- the calibration found no I cells;
- SPEC §10 and EXPERIMENT_STATUS.md recommend new cells in which mid-task information changes the optimal organization.

**Moving to it now would be premature.** A policy that never divides where division pays from t0 is very likely to hit
a floor where division must follow new information, and no live multi-child division has been observed.

**Another full benchmark on the primitive decision is not justified now**, only after a Stage 1 GO. Criterion 2 rests
on the 4 P cells, the treatment's outcome there is nearly certain, and the other 26 cells cannot rescue SUPPORTED once
criterion 2 fires.

**Worth doing now:** Stage 1, whose check is necessary though not sufficient for any I-cell experiment, and offline,
zero-API design and calibration of I cells.

## 9. Recommendation

**Option B: a small clean replication with a scripted `central` and an unchanged `developmental`** (Stage 0-pilot and
Stage 1, 40 live runs).

**Reasons:**
- **The smallest valid step.** It turns an invalid observation into a valid, pre-registered test of criterion 2. It
  changes one arm's definition, fixed entirely by pre-0b artefacts, and declares its scope cuts (4 P cells, no
  `router`, only the urgent part of (v)).
- **It tests the open instrument.** No pilot or 0b run ever divided, so whether live agents realize the designed
  fan-out trade-off in these cells is the instrument E would reuse.
- **It is cheap and declared.** The expected futility stop is declared in advance.
- **The alternatives are weaker:**
  - option C is dominated;
  - option D would hit a floor;
  - option A would leave the hypothesis without a valid test and the instrument unexamined, to save about 200 calls.

**The strongest objection, and the answer.**
- **The objection.** E contains B: a scripted `central` plus an unchanged arm. So B-then-E repeats B's baseline arms,
  and deferring E's wording lets it be chosen after still more data.
- **The answer.**
  - B first avoids building a variant arm on an instrument never seen working live.
  - If E is contemplated, its single variant text should be committed with B's pre-registration, before any B output,
    and run only if B stops at (5).
  - A (stop) is a defensible alternative. It gives up only the instrument check and a valid criterion-2 test.

**Next decisions:**

| outcome | next |
|---|---|
| (5), the expected case | A or one E, never C |
| (4) | A, or a new pre-registered redesign |
| GO | C (Stage 2) |

**Exact go/no-go.**

> Commit Stage 1 iff Stage 0 passes and every Stage 0-pilot `central` run creates its k children, each reading its
> assigned documents.
>
> GO to Stage 2 iff all of the following hold:
> - §7 (1)–(3) hold: completeness; identity and validity; at most one non-intact scripted-`central` run;
> - mean fitness(scripted `central`) > mean fitness(`single`) over the B-urgent runs;
> - the unchanged `developmental` has parallel_rate(P) ≥ 0.50 (≥ 6 of 12 when all complete).
>
> Otherwise NO-GO, with the pre-declared label of §7.

## Limitations

- **The live facts are as reported.** The logs are not in the repository, and the rationale census is not yet
  reported.
- **The probabilities assume independent runs** and simulator-accurate costs. Runs are clustered in 4 cells from 2
  templates, and the oracle assumes perfect aggregation of child reports, so the live (v) check is where the
  calibration is least tested.
- **This memo decides nothing irreversible.** Stage 1 still needs its own pre-registration, the Stage 0 checks, and a
  separate approval before any API call.
