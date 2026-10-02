# Gate 0: offline scientific feasibility (report)

**Decision: FAIL.** Round 1, evaluation 1, is the only evaluation. Its mechanical decision was FAIL, and the round is
closed as FAIL in the audit. No round 2 is registered (§7).

Under the postmortem's stopping rule (EXPERIMENT_0C_POSTMORTEM_AND_NEXT_DECISION.md §10, rule 2), this closes the
formulation. The program stops with zero API calls, and stage A is not authorized.

**What was done.** Everything here is offline and LLM-free:
- no API call;
- no change to any frozen 0b/0c specification, policy, prompt or result;
- no new lifecycle primitive or framework.

**The question.** "Can we construct a small, credible experimental environment in which information-dependent
organizational adaptation has measurable value over strong precommitted alternatives?"

**The answer, for this formulation, is no.** Three results, each read separately below:
1. **The adaptive value is real but small, and confined.**
   - The adaptive oracle A\* beats the best t0 commitment (the router Rt) by 0.032–0.056 fitness at the base point in
     the six urgent template cells, and by 0 in all six relaxed cells.
   - Across the 18-point token grid it ranges from 0 to 0.058.
   - Only A1 and A2 urgent stay at or above δ = 0.03 at every grid point.
2. **Simple deterministic controllers reproduce it.**
   - In every urgent cell, at every grid point, a one-line rule written for the template reproduces A\*: within 0.0065
     for template A, and exactly for template B.
   - The gated one-line generic workflow W\* reproduces one whole template at every grid point. Two decision lines
     reproduce both.
   - No advantage of adaptive ("developmental") organization over a simple precommitted controller can be claimed here.
3. **The follow-up the postmortem asks for cannot be powered.**
   - The gated G9 was not computed, because no cell qualified.
   - Descriptively, treating all six urgent cells as if they had qualified, the deliberation follow-up has power 0.000.
     At the declared checkpoint price, no effect size the runtime allows could make it pay.
   - The presentation follow-up has power 0.009 against the frozen baseline, and 0.115 against the router alone.

Results 2 and 3 were forecast before any evaluation (GATE_0_SPEC.md §4; acceptance.json
`expectation_not_a_criterion`). Round 1 confirms the design analysis rather than discovering something new.

**What the FAIL does not say.** It does not say that this simulator cannot beat the best t0 organization: A1 and A2
urgent beat Rt by ≥ δ everywhere. What fails is beating precommitted workflows with one decision line, and powering a
follow-up.

---

## 1. The comparison (brief Step 1)

**Organizational adaptation** is a change of O(t) after t0, where O(t) is:
- the live agents and their parent relations;
- each agent's assignment;
- the set of agents the root waits on.

It is information-dependent when its occurrence and form depend on what was revealed after t0.

**The operational test uses reveal pairs.** Two worlds, X and Y, are byte-identical before a triage source is read:
same question, catalog, system prompt and brief, and the same event log under any common action prefix. A policy
adapts when all three hold:
- it acts identically in X and Y until the reveal;
- its post-reveal organizational signature differs between them;
- it improves expected net fitness over the precommitted classes.

**The classes** (GATE_0_SPEC.md §2). All share the same information, actions, runtime, costs and limits.

| class | what it is | role |
|---|---|---|
| F, a fixed t0 topology | one plan for every world | dominated by Rt; readable from the fitness tables |
| Rt, the one-shot t0 router | per cell, the best plan whose structure is fixed at t0, by expected value over the reveal pair | gated |
| W\*, the generic workflow | per regime, the best W0 pipeline or one-line rule (one feature, one threshold) over every template world of that regime; rules on revealed features choose only between triage-first pipelines | gated |
| A\*, the adaptive oracle | the best non-anticipating policy: the best common pre-reveal prefix, then each member's best continuation | gated |
| C\*, the optimal contingent policy | equal to A\* within the plan library, because the reveal identifies the member; H\* (clairvoyant) is reported | reference |

**Identifiability.** Nothing can beat the optimal contingent policy with the same observations, actions and cost
model. In a fully specified simulator, a deterministic controller implements it. So the bounded comparison asks two
things:
- Does the value require conditioning the organization on the reveal? Rt cannot do this.
- Does it require more than one precommitted decision line? W\* cannot do this.

**What a positive would have established.** That a system given only general mechanisms produced economically
appropriate, information-dependent reorganization, capturing value no t0 commitment and no one-line precommitted
workflow captures. It would never establish superiority over a workflow written for the task type (§2.1).

**The workflow class is bounded at one line.** That is the brief's "fixed generic workflow reacting via a precommitted
rule". The bound is a modelling choice, and a t0 feature that separates the templates lets the line act as a
per-template switch. That is allowed, because forbidding it would restrict the baseline's information.

## 2. Frozen acceptance and the audit trail (brief Step 2)

**The criteria.** The machine-checkable criteria are `data/gate0/acceptance.json` (version 3), and the prose is
GATE_0_SPEC.md §5. In brief:
- **G1:** integrity, including identical pre-reveal logs.
- **G2:** sanity floors.
- **G3/G4:** at least 4 cells from at least 2 templates in which A\* beats both Rt and W\* by ≥ δ = 0.03 at all 18
  grid points, with divergent signatures.
- **G5:** uneconomic-division controls, including D, a short-document twin of 0b's T01.
- **G7:** a dead-branch release worth ≥ δ.
- **G8:** robustness to six environment perturbations.
- **G9:** follow-up power ≥ 0.80 within 400 runs, for both mechanisms.
- **G10:** the audit.

**The trail.** Everything is on `main`:

| commit / entry | what |
|---|---|
| a264b17 | candidate parameters and the first acceptance file, committed before any simulation |
| 742f713, 7e06654, 9e1600b, 31718d2 | harness, tests and four rounds of pre-genesis amendments, after two adversarial reviews and a final check; no candidate evaluated |
| 29a7dfd | genesis entry `ec505a1a…`, pinning commit 31718d2: acceptance `80cbe516…`, spec `6edbf7f2…`, candidates `5ae31282…`, the 7 world digests, CPython 3.11, the remote and branch |
| beb48d6 | `evaluation_started`, published before anything was simulated |
| c2f01fd | `evaluation_progress` (G1–G8 decision FAIL) and `evaluation_completed` (FAIL); `results.json` `ef973f6b…`, `records.json` `6c2d53d1…` |
| da2e9fc, 91509ea, bb73586, POSTHOC_COMMIT | post-hoc analysis from the logged records (descriptive) |
| DECIDE_COMMIT | `decision` entry: round 1 closed as FAIL |

`python -m devagents.gate0 verify` checks the chain, the pinned hashes, the result and record hashes, the audit's
append-only git history, and that every anchored entry's commit is in HEAD's history.

**Rounds used: 1 of 2. Evaluations: 1.** Every evaluation is logged, and there were no exploratory candidate runs.
Before genesis, only fixture worlds and one timing of 0b's T01 base world were simulated (GATE_0_SPEC.md §6).

**What cannot be enforced** (disclosed in GATE_0_SPEC.md §6):
- Python can call the runtime directly, and git can be configured to misreport.
- Branch protection is not configured from here.
- A published start can be re-run before its completion is published; the evaluation is deterministic.

**Declared deviations** (GATE_0_SPEC.md §6):
1. The criteria and the templates were drafted in the same session, not the criteria first.
2. The follow-up design approximates postmortem §9 in five ways, each favouring feasibility:
   - no non-predictability test;
   - urgent-surface specificity only inside the adaptation contrast;
   - no held-out cells;
   - the router and the workflow merged into one baseline;
   - normal bounds instead of a bootstrap.

## 3. The environment (brief Step 3)

**Execution.** The unchanged discrete-event runtime, with 0b's frozen constants (pinned by hash) and scripted policies
(`devagents/gate0/`). The calibration oracle's conventions apply: fixed allocation rule and oracle step pricing. Only
clean runs count: answered correctly, with every needed fact delivered to the root.

**Template A, "workload reveal" (A1–A3).**
- A cheap SQL triage selects which of 14–16 candidate documents must be read: 7–8 long ones in X (366–432 tokens) or
  7–8 tiny ones in Y (39–58 tokens).
- Division pays in X and is wasteful in Y.

**Template B, "dead-branch reveal" (B1–B3).**
- A slow memo (956–1166 tokens) reveals whether the heavy unit (1363–1511 tokens) is still needed. In X it was
  discontinued; in Y a legacy entity is named instead.
- Starting the heavy unit at t0 pays in Y. In X the oracle releases it while it is still running.

**D.** 0b's T01 with one-paragraph region reports: the stage-A dissociation state.

**The plan library:**
- blind;
- triage then solo;
- triage then fan out over k children, or k children while the root reads a share;
- speculation on k units at t0, then `wait`, `dissolve` (stop waiting for dead units) or `cancel` (also send STOP).

**Release** uses no new primitive. A child the root no longer waits for is terminated when the root answers; its
in-flight charges stand.

## 4. Calibration results (brief Step 4)

### 4.1 Criteria

| criterion | result | reading (GATE_0_SPEC.md §8) |
|---|---|---|
| G1 integrity | **pass** (0 failures) | Reveal pairs identical before the reveal in all 5,904 plan × condition pairs. All prefix groups share one pre-reveal digest. Independently re-derived. |
| G2 sanity | **pass** | — |
| G3/G4 qualifying cells | **fail**: 0 cells (4 from 2 templates required) | The substantive negative (§4.2–4.4). |
| G5 uneconomic division | **fail**, narrowly | D-urgent passes (margin ≥ 0.037). Only A2/urgent/Y clears δ at every grid point; 2 worlds from 2 instances are required. A1/urgent/Y misses by 0.0008 at one grid corner (g0); A3/urgent/Y by 0.005 and 0.003 at g0 and g2. A control is missing in this candidate set. |
| G7 dead-branch release | **pass** | B2 and B3 urgent: releasing the dead unit is worth 0.060 and 0.057 at the worst grid point. |
| G8 robustness | **fail**, vacuously | It counts only G3-qualifying cells, and there are none. It carries no information about fragility. |
| G9 follow-up power | **fail** (not computed) | No qualifying cell. Descriptive power is in §5. |
| G10 audit | holds | `verify` is ok. |

The decision does not hinge on any tie, and the post-hoc re-analysis of `records.json` reproduces every criterion and
number (`analysis/gate0/posthoc_round1.json`).

### 4.2 Absolute fitness at the base point

Each value is the mean over the reveal pair. Fitness is quality minus money and time, scaled by the task's value.

| cell | blind | triage, solo | Rt (plan) | W\* | A\* (X / Y plans) | H\* |
|---|---|---|---|---|---|---|
| A1 urgent | 0.176 | 0.564 | 0.613 (fan2) | 0.604 | **0.656** (fan4 / solo) | 0.656 |
| A2 urgent | 0.175 | 0.564 | 0.613 (fan2) | 0.604 | **0.665** (fan4 / solo) | 0.665 |
| A3 urgent | 0.213 | 0.584 | 0.636 (self+1) | 0.636 | **0.669** (fan4 / solo) | 0.669 |
| B1 urgent | 0.448 | 0.544 | 0.544 (solo) | 0.600 | **0.600** (spec2 dissolve / wait) | 0.605 |
| B2 urgent | 0.434 | 0.522 | 0.555 (spectop1 wait) | 0.607 | **0.607** (spec2 dissolve / wait) | 0.615 |
| B3 urgent | 0.406 | 0.505 | 0.550 (spectop1 wait) | 0.582 | **0.582** (spec2 dissolve / wait) | 0.599 |
| A1–A3 relaxed | 0.78–0.79 | 0.873–0.879 | = solo | = solo | = solo | = solo |
| B1–B3 relaxed | 0.890–0.895 | 0.877–0.883 | = blind | = blind | = blind | +0.002–0.003 |
| D urgent / relaxed | — | 0.835 / 0.930 | solo | — | solo | solo |

### 4.3 Incremental advantage, over the grid and the perturbations

A\* − Rt and A\* − W\* in the urgent cells (relaxed cells: 0 everywhere):

| cell | A\* − Rt at base | min over the grid | A\* − W\* at base | min over the grid | under the 6 perturbations (A\* − Rt) |
|---|---|---|---|---|---|
| A1 | 0.044 | 0.033 | 0.052 | 0.000 | 0.035–0.051 |
| A2 | 0.052 | 0.038 | 0.061 | 0.000 | 0.042–0.060 |
| A3 | 0.032 | 0.022 | 0.032 | 0.000 | 0.023–0.046 |
| B1 | 0.056 | 0.000 | 0.000 | 0.000 | 0.027–0.072 |
| B2 | 0.052 | 0.021 | 0.000 | 0.000 | 0.040–0.068 |
| B3 | 0.033 | 0.015 | 0.000 | 0.000 | 0.025–0.043 |

**How W\* captures the templates.** It captures a different template at different grid points:
- **At 13 of 18 grid points and under all 6 perturbations,** W\*(urgent) is the t0 switch
  `n_units ≥ 8.5 ? W:self+1 (or W:fan4) : W:spec2+dissolve`. The number of units, 14–16 in A and 2–3 in B, separates
  the templates, and the switch reproduces B exactly.
- **At the other 5 grid points** (g9, g11, g13, g15, g17: an extra WORK step at input scale ≥ 1), it is the post-reveal
  rule `needed_read_s ≥ 259.4 ? W:self+1 : W:solo`. That is A's oracle rule; it reproduces A within 0.003.

At no grid point do cells of two templates qualify at once.

**The failure does not depend on W\*.** G4 would fail under every comparator variant tried on the logged records
(`posthoc_round1.json` → `g3_g4_counterfactual`):
- against the router alone: only A1 and A2 urgent qualify;
- against W\* alone;
- against W\* without t0 features;
- against W\* restricted to one pipeline per regime: only A1 and A2 again.

Against the router alone, the result depends on δ and on the grid's extra-step half:
- at δ/2, five cells would qualify (all but B1);
- template B's shortfalls against Rt fall on the grid points with an extra WORK step per agent, which taxes division.

### 4.4 Where the value comes from, and the trivial-rule statement

**Attribution at the base point** (`results.json` → `base.<cell>.attribution`):
- **Template A.**
  - Using the triage information is worth 0.37–0.39.
  - Precommitted division is worth 0.05 over solo.
  - Adapting the divide-or-not decision to the reveal is worth 0.032–0.052. Choosing the shape adds nothing.
  - The adaptation is a single switch: divide (fan4) if the revealed reading is long, otherwise read alone.
- **Template B.**
  - The oracle's group without release (speculate, then wait for everything) is worse than the router by 0.015–0.033.
  - Releasing the dead unit is worth 0.066–0.071, about half of it the money the released child no longer spends.
  - Explicit cancellation costs 0.02 more than simply not waiting.
  - **B's whole advantage over Rt is the release step.** Rt is excluded from it by definition, and it exists as an
    unconditional pipeline in the workflow library (`W:spec2+dissolve`).
- **Parallel execution versus reduced work.** In A the gain is parallel reading in X and avoided division overhead in
  Y. In B it is reduced waiting and spending (release), not parallelism: the router already speculates in B2 and B3.
  No live child is reassigned or redirected in either template (one change point per template).

**The trivial-rule statement the brief requires.** A trivial conditional rule achieves the adaptive oracle's result,
so no advantage for developmental intelligence is claimed. The post-hoc evidence (`typed_rules_vs_oracle`):
- **Template A, urgent.** `needed_read_s ≥ 126.8 ? divide : solo`, with the divided shape chosen per grid point as A\*'s
  is, is within 0.0065 of A\* in every cell at every grid point (0 at 12 of 18).
  - With one shape fixed over the whole grid, the best rule (`needed_read_s ≥ 126.8 ? W:self+2 : W:solo`) falls short by up to 0.036, just over δ. A rule that also
    switches shape on the extra-step cost stays within δ.
- **Template B, urgent.** The unconditional pipeline `W:spec2+dissolve` equals A\* exactly.
- **Relaxed.** `W:solo` (A) and `W:blind` (B) equal A\*.

**The frozen D1/D5 disclosure.** It reads `reproduces_oracle_within_delta: false`, and that value is vacuous: it is
computed only over qualifying cells, and there are none. The post-hoc numbers above are the meaningful ones.

## 5. Follow-up feasibility and power (brief Step 5)

> Simulator-derived and conditional on declared assumptions (GATE_0_SPEC.md §7). Nothing here is evidence about an
> LLM, and nothing here is empirically established.

**Status.** The gated G9 was not computed, because no cell qualified. To answer Step 5 anyway, the frozen power model
(`devagents/gate0/power.py`, unchanged) was run descriptively on the six urgent template cells as if they had
qualified. Two baselines were used: the frozen one (the better of Rt and W\* per cell), and Rt alone, which is the most
favourable.

**The design.**
- **Arms:**
  - M, the mechanism;
  - B, the scripted baseline;
  - N, the no-LLM controller;
  - ABL, M with the revealed state hidden;
  - A, the scripted oracle;
  - M on 12 validated relaxed control worlds.
- **Cells:** 6 cells, both members each.
- **Allocation:** searched within 400 runs for each mechanism.

| | presentation, frozen baseline | presentation, Rt only | deliberation (either baseline) |
|---|---|---|---|
| allocation (R_M, R_B = R_N, R_ABL, R_S) | 6, 8, 3, 4 | 6, 8, 4, 3 | 6, 4, 2, 2 |
| runs | 360 | 360 | 228 |
| **joint power, primary** | **0.009** | **0.115** | **0.000** |
| joint pessimistic scenario | 0.001 | 0.009 | 0.000 |
| power at the grid-minimum effects | 0.000 | 0.039 | 0.000 |
| API calls / list-price $ / sequential hours | 2,152 / $36.09 / 4.8 h | 1,960 / $34.19 / 4.4 h | 1,868 / $50.07 / 8.4 h (frozen); 1,772 / $49.12 / 8.2 h (Rt only) |

The cost figures charge the oracle's plan and its mean checkpoints to every M, ABL and control run. They are upper
bounds: under the model's own failure assumptions the expected deliberation cost is about $42 and 6.9 h.

**Why each mechanism fails.**
- **Presentation.** M − B averages only 0.016 against Rt, and below 0 against the frozen baseline. A non-adapting run
  falls back to the 0b/0c default (triage, then solo), which is up to 0.05 below Rt (0 in B1, where Rt is solo).
  - Against the frozen baseline no effect scaling helps, because W\* already equals A\* in all three B cells: at 3× the
    effects, power is 0.055.
  - Against Rt alone, effects about 3× larger give 0.78 to 0.84, depending on the allocation.
- **Deliberation.** A run pays one high-effort checkpoint per general event of the plan it runs: t0, the reveal, and
  each child's termination.
  - That is 2–6 checkpoints, each 0.147 fitness when urgent: 0.29–0.88 per run. Arm B pays none.
  - For M − B to be positive in expectation, the oracle must beat the baseline by at least about 0.47 in urgent cells.
    Power 0.80 needs about 0.65–0.70.
  - The observed effects are at most 0.06, and 0.10 over the default.
  - G2 bounds what any candidate set could offer. With G2's floor of 0.3 on solo-type plans, k children can cut the
    solo plan's cost by at most a factor of k + 1. That caps the advantage at 0.7·k/(k + 1), which stays at least 0.19
    below the requirement (about 0.40 + 0.147·k) at every k, even with free children. At the measured cost of about
    0.043 per child, the cap is about 0.35–0.39.
  - So deliberation power is 0.000 at every checkpoint size from 250 to 4,000 output tokens.

**What assumptions would give power ≥ 0.80** (presentation, Rt-only baseline, these cells):
- No single departure in the declared one-at-a-time table reaches 0.80. The highest is 0.75, when only the baseline
  arms fail at 12%.
- Joint settings inside the declared ranges do cross it. Each of these reaches 0.81–0.96:
  - π = 1 with no answer failures;
  - π = 1 with effects × 2;
  - η = 0 with effects × 3;
  - π = 0.9 with baseline failures at 12%.

  Each requires the mechanism to adapt almost perfectly, or the baseline to fail more often than the mechanism, or
  effects 2–3 times what this environment produced.
- **Deliberation: no assumption set within the declared ranges.** Even oracle plans at fitness 1.0 do not pay for the
  checkpoints.

**Sensitivity tables:** `posthoc_round1.json` → `followup_if_urgent_cells_qualified` contains:
- the one-at-a-time sensitivity in π, σ, the failure rates, ρ, s, τ_sim, η, s_ctl and q_default;
- the π × σ grid;
- the effect scaling;
- size under the null.

## 6. Adversarial validation (brief Step 6)

A five-lens adversarial review (41 agents, each finding re-checked by an independent verifier) worked from the logged
records and from its own fixture worlds. It re-derived every gated value independently, with 0 mismatches. It found no
implementation defect that changes a criterion. It found three defects in the post-hoc script and several overstated
readings; all are corrected in this report and in `posthoc_round1.py`. Its answers to the brief's questions:

1. **Does the environment require adaptation?** Only narrowly.
   - Urgent cells: A\* beats Rt by ≥ δ with divergent signatures at the base point. At every grid point, that holds
     only in A1 and A2.
   - Relaxed cells: no adaptation is needed.
   - What is required is one contingent switch per template, worth about a tenth of what using the triage information
     is worth.
2. **Can a one-line rule solve it?** Yes.
   - Per template: A within 0.0065, B exactly (an unconditional pipeline).
   - Generic: a single line with no t0 feature still captures one template at every grid point.
   - Two lines capture both.
3. **Is the workflow baseline weak?** No. W\* is, if anything, optimistic: it is chosen with hindsight per condition,
   in-sample, and may switch per template. The weak comparator is the router in B, and that is definitional: Rt may not
   release.
4. **Does the oracle have privileged information?** No world information beyond the reveal.
   - The one privileged read, `cancel`'s status peek, is never used by A\*.
   - A\* knows exact fitness and reasons perfectly, as do Rt, W\* and the typed rules. This does not bias the gaps, but
     it makes absolute fitness, and π in the power model, upper bounds.
5. **Are costs consistent?** Yes. Every class is read off the same run records through the same runtime and constants.
   - The grid's extra-WORK-step axis charges every agent and taxes division alike for all classes; it causes most of
     the points below δ.
   - The deliberation checkpoints are charged only to the mechanism arms, by design.
6. **Are the pairs identical before the reveal?** Yes, verified independently.
   - Pre-reveal digests, reveal times and t0 states are identical across all 5,904 plan × condition pairs present
     in both members.
   - Catalogs and questions are identical, and only the triage source differs.
   - The root brief is not in `records.json`. It is member-invariant by construction and was checked during the run.
7. **Is the result robust?** The FAIL is robust:
   - G3/G4 fails under every comparator variant, pointwise at every grid point and perturbation, and the re-analysis is
     bit-identical.
   - G5 is a narrow miss, G8 is vacuous, and the router-only negative depends on δ.
8. **Does it overfit the mechanism?** By design, yes. The templates were sized analytically to give an A\* − Rt gap of
   about 0.05, and the gap observed is 0.032–0.056. Each template has one change point, at the reveal. The negative
   covers two templates, two levers (concurrent reading and release) and one round.
9. **Can it produce an informative negative?** Only partly.
   - The headline G3/G4 failure and the deliberation infeasibility were forecast before evaluation; they confirm the
     design analysis.
   - What is new is the magnitudes:
     - small effects;
     - zero value when time is cheap;
     - B's fragility against Rt when steps cost more;
     - the G5 near-miss;
     - the unpowered presentation follow-up.

## 7. Decision (brief Step 8)

**Round 1: FAIL**, decided in the audit as the mechanical decision requires. It failed G3/G4, G5, G8 (vacuously) and G9
(not computed).

**No round 2.** The spec permits one after a round-1 FAIL. It is not registered because no round-2 candidate set could
pass:
- **G9 cannot pass for any candidate set that passes G2.**
  - The deliberation half needs an oracle advantage of about 0.65 or more over the baseline in urgent cells (relaxed:
    about 0.40). Relaxed effects were 0 throughout. In urgent cells, G2's floor caps the advantage below what is
    needed at every child count (§5).
  - The presentation half needs about 0.10–0.15. A search of about 18,000 of the reviewers' own fixture designs (never
    candidate-derived) found at most 0.119 (SQL triage) and 0.145 (memo triage) over Rt. In every design that reached
    that level, a single W0 pipeline reproduced the oracle, so A\* − W\* = 0.
- **The G3/G4 failure is structural.**
  - Each template's oracle policy is itself in the one-line class, so W\* captures a whole template at every grid
    point.
  - Typed one-line rules capture both templates.
  - A round-2 set could escape only by being designed against that bound. A PASS obtained that way would still carry
    the disclosure that a simple typed rule reproduces A\*.
- **The time box was not the reason.** The work took under 12 hours of wall-clock time from the postmortem commit,
  within the brief's two-day time box.

**What this authorizes.** FAIL closes this formulation under postmortem §10, rule 2: "Gate 0 fails → the program stops,
with zero API calls."
- Stage A is not authorized.
- No API call is authorized.
- No follow-up is authorized.
- The postmortem's tripwire (rule 6) is unaffected.

## 8. The Experiment 0c ledger

The sha256 of `results/exp0c/stage1/stage1_decision.json` is still not recorded. That file is local to the
experimenter's machine and gitignored, and it is not in this checkout. It is not invented here. To record it, run this
in the experimenter's checkout (Windows `py`, or `python3`):

```
py -c "from devagents.evals.exp0c import sha256_lf; print(sha256_lf('results/exp0c/stage1/stage1_decision.json'))"
```

## 9. Limitations and disclosures

- **The oracle's perfect reasoning and exact model knowledge.** Only information flow is checked.
- **The latency constants.** They are declared assumptions, validated live only for 0c's t0 fan-out.
- **Child reports are a fixed 21-token string,** a convention inherited from the 0b calibration. It understates the
  cost of division slightly, which matters for G5's narrow miss: the bias is toward division, so it makes G5 harder to
  pass.
- **`dissolve` waits with WAIT `any`.** This can cost one extra root step per separately arriving needed report. It is
  conservative, and it is zero in the plans A\* chose.
- **G1 gaps.**
  - `records.json` omits the root brief.
  - G1 does not compare reveal times within prefix groups, or for plans present in one member only. Both hold in the
    records.
- **Tie labels.** In B's Y member, `wait`, `dissolve` and `cancel` are identical runs; the frozen analysis labels the
  tie `wait`.
- **The post-hoc files sit outside the post-genesis allowlist.** They are `analysis/gate0/posthoc_round1.py` and
  `.json`, and they would block a round-2 registration unless removed. They do not affect the closed round 1.
- **The negative is scoped.** It covers two templates, the concurrent-reading and release levers, one change point per
  template, one round, and this runtime's cost model. A different testbed would be a new proposal (postmortem §10,
  rule 7).

## 10. Files

| file | what |
|---|---|
| `GATE_0_SPEC.md`, `data/gate0/acceptance.json` | the frozen specification and criteria |
| `data/gate0/candidates_round1.json` | the round-1 candidate parameters |
| `devagents/gate0/` | worlds, plans, classes and criteria, power, audit, CLI (`python -m devagents.gate0`) |
| `tests/test_gate0.py` | 37 tests, including the anchored trail on a scratch git repository |
| `data/gate0/audit.jsonl` | the append-only, hash-chained audit |
| `data/gate0/round1/eval1/results.json`, `records.json` | the evaluation's analysis and every run record |
| `analysis/gate0/posthoc_round1.py`, `.json` | the descriptive post-hoc analysis (logged records only) |
