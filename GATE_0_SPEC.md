# Gate 0: offline scientific feasibility (specification)

**Status.** Frozen before any candidate world was simulated. The machine-readable criteria are
`data/gate0/acceptance.json` (version 2). The genesis entry of the append-only audit `data/gate0/audit.jsonl` pins the
LF-normalized SHA-256 of that file, of this document and of the round-1 candidate file, together with the git tree
hashes of the code that defines the classes and criteria. It is written before the first calibration evaluation, on a
clean, pushed commit. If this document and acceptance.json disagree, acceptance.json governs.

**Scope.**
- Gate 0 only, as specified in EXPERIMENT_0C_POSTMORTEM_AND_NEXT_DECISION.md §8 and §10, with the deviation declared
  in §6.
- It makes zero API calls and runs no LLM, and it implements neither stage A nor stage B.
- It does not change frozen 0b/0c specifications, policies, prompts or results. `devagents/__main__.py`, which 0c's
  pre-registration pins, is unchanged; Gate 0 has its own entry point, `python -m devagents.gate0`.
- It adds no new framework and no new lifecycle primitive.
- Everything runs through the unchanged discrete-event runtime as scripted policies (`devagents/gate0/`).

**The question.** Can we construct a small, credible experimental environment in which information-dependent
organizational adaptation has measurable value over strong precommitted alternatives? This is a test of the
*testbed*, not of any model.

## 1. What counts as organizational adaptation

**The organization.** At time t, the organization O(t) is:
- the set of live agents and their parent relations;
- each agent's assignment;
- the set of agents the root is waiting on.

**Organizational adaptation.** A change to O(t) after t0: creating agents, changing the waiting set, or releasing
work. It is *information-dependent* if both its occurrence and its form depend on information revealed after t0.

**The operational test uses a reveal set.** A reveal set is two worlds (members X and Y) that are byte-identical
before the reveal:
- the same question and catalog;
- the same system prompt and brief;
- the same event log under any common prefix of actions.

They differ only in what one *triage source* returns. Adaptation is demonstrated when an adaptive policy satisfies
all three of these conditions:
- it is **non-anticipating**: it takes identical actions in both members until the reveal;
- it **reorganizes differently** in X and Y after the reveal: its post-reveal organizational signature differs;
- it **improves expected net fitness** over the best t0 commitment *and* over the best generic workflow.

The signature counts children spawned before the reveal, children spawned after it, and children released while still
running.

**Static division is not development.** A topology chosen at t0 never counts, however good it is.

## 2. The comparison classes

All classes use the same information access (any agent may read any source), the same action space, the same
execution semantics and cost accounting (the runtime), and the same resource limits. They differ only in **when an
organizational decision is fixed, and on what it may depend.**

1. **Fixed topology at t0 (F).** One plan applied to every world. It is reported, not gated: the router dominates
   it.
2. **One-shot router (Rt).** Per cell, the best plan *of the plan library* whose organizational structure is fixed at
   t0, chosen to maximize the expected fitness over the reveal set: the Bayes-optimal t0 router over the library, with
   a known uniform prior, re-optimized at every grid point.
   - Its *content* may use the reveal by a fixed rule: a `triage>fan<k>` plan hands the needed documents to k
     children in size-balanced shares.
   - Its structure may not use the reveal: it cannot change k, it cannot choose between solo and divided, and it
     cannot release a child.
   - Rt is not the runtime's `router` mode, which restricts only *when* SPAWN may happen.
3. **Generic workflow (W\*).** For each regime, the best single workflow applied unchanged to every template world of
   that regime. The class is the union of two kinds:
   - every pipeline of the W0 library: blind reading; triage then solo; triage then fan out over what the triage
     selects (fixed k, one child per item, or k children while the root reads a share); count-contingent fan-out;
     speculative fan-out over all candidate units; and speculation that **releases units the triage rules out**;
   - **every one-line rule.** A rule has one feature: the number of candidate units, catalog documents or needed
     documents, or the listed reading time of the candidates, of the needed documents, or of the largest needed
     document. It has one global threshold, placed at a midpoint between observed feature values, and it chooses
     between two W0 pipelines. A rule on a feature revealed by the triage may choose only between triage-first
     pipelines, which share their pre-reveal actions.

   Because W\* is chosen per regime, it may also branch on the stated value of time. W\* is thus the strongest
   *generic* precommitted policy with one decision line, and the class contains the obvious size-contingent and
   urgency-contingent map-reduce rules.
4. **Adaptive oracle (A\*).** The best *non-anticipating* policy over the plan library.
   - Plans are grouped by their common pre-reveal prefix. The group with the highest expected value is chosen, then
     each member gets that group's best continuation.
   - The logs verify that every plan in a group is identical before the reveal, in every member and condition.
   - A\* sees nothing a member has not revealed. It "reasons perfectly" exactly as the calibration oracle does, and
     the log must show that every needed fact reached the root before it answered.
5. **Fully optimal contingent policy (C\*).** A theoretical reference, not a comparator. Within the library C\* = A\*,
   because each reveal identifies its member. The clairvoyant H\* (the best plan per world) is reported. Library
   coverage is the only bound on what C\* could add.

**Disclosed, not gated** (§5, D1–D5):
- **W_typed:** the best W0 pipeline per cell.
- **Typed one-line rules:** rules fitted on one template's worlds alone.
- **Priors 0.25 and 0.75:** A\* − Rt under unequal priors.

### 2.1 Identifiability, and why the comparison is bounded where it is

**Nothing here can beat C\*.** A policy with the same observations, actions and cost model cannot beat the optimal
contingent policy. In a fully specified simulator, a deterministic controller that knows the cost model and the
template's structure implements A\*. Gate 0 therefore claims **no** advantage of "developmental intelligence" over such
a controller.

**What the gated comparison asks.** It asks two things:
- Does the value require *conditioning the organization on the reveal*? Rt is typed per task but cannot do this.
- Does it require *recognizing which kind of situation one is in*? W\* conditions on the reveal and the regime but is
  one workflow for every task.

**What a positive result would establish, and what it would not.**
- **It would establish** that a system given only general mechanisms autonomously produced economically appropriate,
  information-dependent reorganization, capturing value that no t0 commitment and no one-line generic workflow
  captures on these cells.
- **It would not establish** superiority to a precommitted workflow written for the task type (W_typed, typed one-line
  rules). Such a workflow is, by construction, "architecture specified in advance by a human". The north-star claim is
  *autonomy*: doing as well without that specification.
- **The disclosures D1 and D5 report how simple that typed workflow is.** If a typed one-line rule reproduces A\*, the
  report says so, and no claim beyond autonomous adaptation is licensed.

**The postmortem's §6.0 test 7.** That test says "the LLM beats a no-LLM controller running the mechanism's own rule".
It is meaningful only if that controller is the mechanism's scaffolding with a fixed default decision. If the
controller computes the economics, the test is unpassable by construction. §7 models it that way.

## 3. The environment

**Runtime and constants.**
- Experiment 0b's frozen constants, pinned by hash. The urgent value of time is 0.0016 score per second, and each
  document costs 3 s plus 0.1 s per token.
- The calibration oracle's conventions: `developmental` mode, the fixed allocation rule (`fixed_rule_spawns`, an equal
  share of 50% of the balance per child), and oracle step pricing at the frozen r = 2.0052 and 36 reasoning tokens.
- Fitness is `calibrate._fitness`. Only *clean* runs count: answered, quality 1, every needed fact delivered to the
  root before it answers, no invalid action, no cap hit, no starvation, no expired lifetime. An unclean plan is
  infeasible at that condition.

**The plan library** (`devagents/gate0/plans.py`, generic and instantiated per member):
- `blind`;
- `triage>solo`;
- `triage>fan<k>`;
- `triage>self+<k>` (k children, and the root reads a share);
- `spec<k>>{wait|dissolve|cancel}`;
- `spectop<m>>{wait|dissolve|cancel}`.

Template A's speculative children triage for themselves; this is the calibration's `atstart-k`. Work is assigned in
size-balanced shares: largest first, on the catalog's token counts, which are identical across members.

**Waiting and releasing.** `wait` waits for every child. `dissolve` waits only for children that hold a needed unit,
and `cancel` also sends a STOP message to children that hold only dead units. All three send WAIT only while a child
they wait for has not reported, so they differ only in whom they wait for.

**No new lifecycle primitive.**
- **How work is released.** A released child is terminated by the runtime when the root answers, and its in-flight
  charges stand. Because charges post when an action starts and the run ends at the answer, the value of release is
  almost entirely *not waiting*.
- **Explicit cancellation** (a STOP message, the child terminating at its next step) is priced separately. It rarely
  helps, and the report shows by how much.
- **One privileged read.** `cancel` reads a child's termination status about 0.5 s before the root could know it, only
  to avoid an invalid MESSAGE. This is disclosed. Cancellation is dominated anyway.

## 4. Templates and the round-1 candidate set

The parameters are in `data/gate0/candidates_round1.json`, committed in a264b17 before any simulation and pinned at
genesis.

**Template A, "workload reveal".** It models a cheap investigation that reveals how much downstream work exists.
- A cheap SQL triage selects which of 14–16 candidate documents must be read.
- In member X the selected documents are the long ones (360–420 tokens). In member Y they are the tiny ones (35–40
  tokens). The count and the catalog are the same.
- After the reveal, division pays in X and is wasteful in Y.
- Instances A1–A3 cover three domains.

**Template B, "dead-branch reveal".** It models a slow memo that reveals whether a long workstream is needed.
- A slow memo (950–1150 tokens, about 100–120 s to read) reveals whether the heaviest work unit (1350–1500 tokens) is
  still needed.
- In X the memo discontinues the heavy unit. In Y it names a legacy entity: it is listed in the structured source,
  has no report, and its name is as long as the heavy unit's.
- Starting the heavy unit at t0 pays in Y. In X, the oracle releases it while it is still running.
- Instances B1–B3 cover three domains.

**D.** Experiment 0b's T01 (same question, same document ids), with every region report shortened to one paragraph.
It is the stage-A dissociation state, calibrated here only, and never a follow-up cell.

**Answers.** Every template answer is numeric, so guessing scores about 0.

**Disclosed design regularities** (an LLM could learn them; the oracle is unaffected):
- The reveal pairs are the two extremes of their template.
- In B, the memo can kill only the heavy unit, and the heavy unit carries the maximum value.

**Analytic expectation, recorded before evaluation (not a criterion).**
- The oracle's advantage over the best t0 commitment was estimated at about 0.04–0.06 for both templates.
  Non-anticipation halves the value of adapting, and each child costs about 0.045 fitness (about 28 s of urgent time).
- After the pre-genesis review, a further expectation was recorded: each template's oracle policy is a one-line
  contingent rule (A: urgent and long revealed reading → fan out; B: urgent → speculate and release ruled-out units).
  So the per-regime generic workflow may capture one template's value, and G4 (two templates) may fail.

**A FAIL is a live outcome.**

## 5. Frozen acceptance criteria

δ = 0.03. A **cell** is an instance × regime, with its reveal set. The **grid** is the 18-point token grid of the 0b
calibration (`calibrate.grid` of the frozen assumptions). The **perturbations** are six single-factor changes at the
base tokens:
- document latency (base and per-token parts) × 0.8 and × 1.25;
- value of time × 0.8 and × 1.25;
- all coordination fees × 2;
- message latency × 4.

| id | criterion |
|---|---|
| **G1 integrity** | Every plan is clean in every world at the base point, and every plan without children is clean at every grid point. Every member of a reveal set has the same t0 state (system prompt and brief), the same reveal time, and identical logs before the reveal for every plan. Within a prefix group, plans have identical logs before the reveal. Members differ only in the triage source, and what it reveals differs. |
| **G2 sanity** (0b gate d) | At the base point, in every template world and in D: best fitness ≥ 0.5, and best fitness without children ≥ 0.3. |
| **G3 qualifying cell** | A template cell qualifies if, at **every** grid point: A\* − Rt ≥ δ; A\* − W\* ≥ δ (W\* of the cell's regime); and A\*'s post-reveal signature differs between X and Y. |
| **G4 count** | At least 4 qualifying cells, from at least 2 templates with at least 2 qualifying cells each. |
| **G5 uneconomic division** (the dissociation from "spawn iff urgent and several documents") | D-urgent: the best plan without children beats every plan with children by ≥ δ at every grid point. Also, at least 2 urgent template worlds needing ≥ 2 documents, from at least 2 instances, satisfy the same condition. |
| **G6** | Withdrawn before genesis (see §6, amendment 3). |
| **G7 dead-branch release** | In at least 1 cell, at every grid point, A\*'s policy releases a still-running child in at least one member, and that is worth ≥ δ over the best plan of the same prefix group that releases nothing. |
| **G8 robustness** | Under each perturbation, the G4 counts still hold among the G3-qualifying cells, with both advantages ≥ δ/2 and A\* still diverging. |
| **G9 follow-up power** | The pre-declared follow-up (§7), with the presentation mechanism, fits in ≤ 400 runs and reaches joint power ≥ 0.80 under the primary assumptions. |
| **G10 audit** | The hash chain is intact, and the acceptance, spec, candidate and code hashes match genesis. There are ≤ 2 rounds, and every evaluation is logged. It is enforced by `begin_evaluation`; a violation aborts the evaluation. |

**Mandatory disclosures (not gates).**
- **D1/D5:** for each template and regime, the best typed one-line rule, its expected shortfall in every qualifying
  cell, and whether it reproduces A\* within δ in all of them at any grid point.
- **D2:** W_typed against A\* in each cell.
- **D3:** H\* − A\*; C\* = A\* within the library.
- **D4:** the attribution of A\*'s value, separating:
  - information use without reorganization (`triage>solo` − `blind`);
  - precommitted division;
  - adaptive reorganization, split into divide-or-not, choice of shape, speculation, dead-branch release and explicit
    cancel.
- **Priors:** A\* − Rt at priors 0.25 and 0.75.

### 5.1 Ambiguities resolved before evaluation, and why

- **Advantage per cell, or per member?** It is the **expectation over the reveal set**. A t0 router must make the same
  choice in both members, so it is right in one member by construction; a per-member gap would compare A\* with a
  router that has privileged knowledge. The expected gap is the decision-theoretic value of adapting organization to
  the reveal.
- **"The best fixed generic workflow".** It is **one workflow per regime for every template**, including every one-line
  contingent rule. "Generic" means not specialized to the task. Choosing it with hindsight at each condition and
  allowing a regime branch makes it as strong as the class allows. A per-task workflow (W_typed, typed rules) is
  architecture specified by a human for that task type, so it is disclosed, not gated (§2.1).
- **"At every grid point".** This means the 0b token grid, as in the postmortem. Environment constants are checked
  separately at δ/2.
- **"At least two templates".** The requirement is two templates **with two qualifying cells each**.
- **"Defeats the simple rule 'spawn iff urgent and multiple documents'".** This is G5. It requires urgent,
  multi-document states, including D, in which every plan with children loses by δ. It is the behavioural
  dissociation that the postmortem's stage A and follow-up use.
- **"Opportunity for redirection or termination".** The release must actually happen and be worth ≥ δ (G7).
- **Sanity floors.** The 0b gate (d) values are kept unchanged.

## 6. Audit rules

**The trail.**
- **The audit file.** `data/gate0/audit.jsonl` is append-only and hash-chained (`devagents/gate0/audit.py`).
- **Anchoring.** The chain detects edits but not truncation or deletion, so the official audit is anchored to git:
  - genesis requires a clean tree whose HEAD is on the remote;
  - every evaluation requires the audit file to equal its committed version at a pushed HEAD.

  So every entry must be committed and pushed before the next evaluation.
- **What genesis pins:**
  - the hashes of acceptance.json, this document and candidates_round1.json;
  - the git tree hashes of `devagents/`, `tests/`, `data/world`, `data/exp0b/frozen.json`, the acceptance and
    candidate files, this document and `pyproject.toml`.

**Rounds.**
- **A round** is one candidate set. Round 1 must be the file pinned at genesis, run on the code pinned at genesis.
- **At most 2 rounds.** Round 2 may be registered only after round 1 ends in FAIL; its code trees are recorded when it
  is registered.
- **Re-evaluation.** A round is evaluated once. It may be re-evaluated only after a verified `defect` entry: an
  existing commit that descends from the evaluated code and is in HEAD, plus a regression test that exists. The
  re-evaluation must use the same candidate file and identical world digests; a change to the worlds is a new round.
  At most 2 re-evaluations, and every evaluation stays in the log, each in its own directory
  (`data/gate0/round<N>/eval<k>/`).
- **Order and crashes.** `calibrate` validates its inputs, appends `evaluation_started` before any simulation, and
  appends `evaluation_completed` with the results file's hash and the mechanical decision. A crash appends an
  INDETERMINATE completion.
- **Closing.** `decide` closes a round and must repeat its last mechanical decision. Thresholds are never changed
  after any output.
- **Commands.** Only `verify` may name another audit file.

**What cannot be enforced, and other disclosures.**
- **Unlogged simulation is physically possible.** Python can call the runtime directly, so enforcement is procedural,
  backed by the anchored chain and the git history.
- **What the commit history shows.**
  - The candidate file was committed and pushed (a264b17) before any simulation; the harness existed uncommitted at
    that moment.
  - Before genesis, only fixture worlds were simulated: the instances in `tests/test_gate0.py` and the reviewers' own
    small fixtures, whose parameters differ from every candidate. They were used to test code, not to choose
    candidates.
- **A round 2, if any,** would be designed with knowledge of round 1's records and diagnosis. A round-2 PASS carries
  less evidential weight than a round-1 PASS.
- **Declared deviation from postmortem §8.** §8 asked for the grid, δ and the criteria to be hashed before any
  template was designed. Here acceptance.json and the round-1 templates were drafted in the same session and first
  committed together (a264b17). The W0 library and the rule features were written with the templates in view. The
  guarantee offered instead is that both were frozen before any candidate evaluation.

**Pre-genesis amendments** (all made before any candidate evaluation; none prompted by candidate output):
1. **Control replication.** It is searched instead of being fixed at 2. A fixture test showed that a fixed R_S = 2
   made the spawn-rate check fail in about 7% of simulations by itself.
2. **Accuracy interval.** It became Agresti–Caffo instead of Wald, because Wald collapses when an arm makes no error.
   It was later superseded by amendment 3's raw-fitness analysis.
3. **Prompted by an adversarial review of the spec and harness** (5 lenses; 38 of 39 serious findings confirmed):
   - **A WAIT artifact was fixed.** `wait` spent a redundant step that let a no-op "dissolve" gain about δ. G7 now
     requires an actual release, measured against the best non-releasing plan.
   - **Shares are size-balanced.** They were round-robin, which gave one child every long document.
   - **Root-share plans** (`triage>self+k`) were added.
   - **The generic workflow is stronger.** It is per regime and includes every one-line rule, in place of a single
     pipeline pooled across regimes.
   - **G6 (rule dissociation) was withdrawn.** As written, it was pooled across templates, counted a cell as defeated
     when either member fell short, and could not fail independently of G3/G4. The legitimate part, defeating one-line
     generic rules, now lives in W\*. The typed version is disclosed (D1/D5), because a rule written per task type is
     human-specified architecture.
   - **G8 now also requires divergence,** and the document-latency perturbation scales both latency parts.
   - **The power analysis was rebuilt (§7).** It now has raw fitness, fixed-cell inference, a per-template contrast,
     an ablation arm, the 0b/0c default as M's failure mode, and priced deliberation.
   - **The audit was hardened** (this section).

## 7. The follow-up and its power

The follow-up is designed now and pre-registered later. No run of it is authorized.

**Cells.**
- **Information-dependent cells:** every G3-qualifying cell, with both members.
- **Controls:** the relaxed twins of the qualifying instances, kept only where division clearly does not pay
  (the best plan without children wins by ≥ δ).

**Arms.**
- **M:** the mechanism; the LLM organizes.
- **B:** per cell, the better of Rt and W\*, with a scripted organization and LLM content work. B dominates every
  fixed-plan heuristic of postmortem §6.0 test 7, because those choose fixed plans at t0, and Rt is the best fixed plan
  per cell.
- **N:** the no-LLM controller: the mechanism's scaffolding with a fixed default. It is modelled like B, which is
  conservative.
- **ABL:** M with the revealed state hidden, for postmortem test 6.
- **A:** the scripted oracle, 1 run per world, as an instrument check.
- **M on controls.**

**Analysis.** The qualifying cells are treated as fixed cells; no population or template-level generalization is
claimed. All of the following must pass:
- **F1:** per template, the adaptation contrast is ≥ 0.30 with a normal lower bound > 0. The contrast is
  P(reorganization on A\*'s X–Y axis | X) − P(the same | Y), with labels derived from A\*'s own signatures.
- **F2:** raw fitness, M − B over cells and members, has a lower bound > 0 (within-cell variances), and every
  template's estimate is > 0.
- **F3:** the spawn rate on controls is ≤ 0.20.
- **F4:** F2 against N.
- **F5:** M's contrast exceeds ABL's, with a lower bound > 0.

**Generative model** (`devagents/gate0/power.py`):
- In each run, M takes A\*'s plan with probability π_c. Otherwise it falls back, with probability q_default, to the
  0b/0c default (triage, then read alone), and else to B's plan.
- logit π_c = logit π + s·(√ρ·z_template + √(1−ρ)·z_cell).
- Noise N(0, σ²) is added to every run.
- M's runs also carry a cell bias N(0, τ_sim²) and an overhead η.
- A wrong answer costs 1.0 (p_fail, and p_fail_M for M).
- M spawns on a control world with probability s_ctl.
- The effects are the base-point fitness of the plans, from calibration.

**Primary assumptions.**

| parameter | primary value |
|---|---|
| π | 0.8 |
| s | 1.0 |
| ρ | 0.5 |
| σ | 0.05 |
| p_fail | 0.02 |
| p_fail_M | 0.02 |
| τ_sim | 0.02 |
| η | 0.01 |
| s_ctl | 0.10 |
| q_default | 0.5 |

Justification:
- In 0c, the live B-urgent means of `single` and scripted `central` landed within 0.012 of their offline predictions,
  with no visible answer failures in 24 runs. With 0 failures in 24 runs, the 95% upper bound on the failure rate is
  about 0.12, which the pessimistic set uses.
- π = 0.8 is the alternative of interest ("the mechanism mostly works"), not an estimate.
- q_default = 0.5 reflects 0b/0c's observed default (0/192 spawns).

**Mechanisms.**
- **G9 gates the presentation mechanism.**
- **The deliberation mechanism** is charged per run for 2 checkpoints, each with 2,000 output and 4,000 input tokens,
  priced by the runtime's own money and latency model: about 0.24 fitness urgent and 0.12 relaxed. Its power is
  reported.
- **Pre-declared consequence:** if the deliberation variant's power is below 0.80, a deliberation-mechanism follow-up
  is infeasible. Should stage B select a high-effort arm, there is no follow-up and the program stops.

**Allocation and Monte Carlo.**
- A fixed search over R_M, R_B = R_N, R_ABL and R_S, within 400 runs.
- The search seed differs from the final seed.
- On near-ties within one Monte Carlo standard error, the search prefers more control replication, then fewer runs.
- The final estimate uses 4,000 simulations.

**Reported alongside the power:**
- one-at-a-time sensitivity in π, σ, p_fail, p_fail_M, ρ, s, τ_sim, η, s_ctl and q_default;
- a π × σ grid;
- a pessimistic set: s = 3, p_fail = 0.12, p_fail_M = 0.06, σ = 0.08, η = 0.02, q_default = 1, effects × 0.8, and the
  minimum effect over the grid;
- size under the null;
- API calls, list-price spend and sequential wall time for both mechanisms.

**What the power is not.** It is conditional on declared assumptions, never empirically established.

## 8. Decision

- **INDETERMINATE** if G1 fails or the evaluation cannot complete. The report then states what remains unresolved and
  what resolving it would cost.
- **PASS** if every gated criterion holds.
- **FAIL** otherwise.

**Rounds.** Round 2 may follow a round-1 FAIL, with a revised candidate set justified by the diagnosed failure. The
criteria never change. A round-2 FAIL is final.

**What each outcome authorizes.**
- **PASS** authorizes only a review of Gate 0. It does not authorize stage A.
- **FAIL** closes this formulation of the research program under the postmortem's stopping rule (§10, rule 2: "Gate 0
  fails → the program stops, with zero API calls").

**How a FAIL is read.** The report must say which criterion failed and read each failure separately:
- **G3/G4:** the adaptation's value is captured by a t0 commitment or by a generic one-line workflow. This is the
  substantive negative.
- **G2, G5 or G7:** a control or opportunity is missing in this candidate set.
- **G8:** fragility.
- **G9:** the follow-up is not powered.

A negative covers two templates, the concurrent-reading and release levers, and at most two rounds.

## 9. Known limitations, stated in advance

- **The oracle's perfect reasoning.** Only the information is checked; content work is assumed correct.
- **The latency constants.** The declared LLM latency and per-document latency are assumptions. They were validated
  live only for 0c's t0 fan-out, not for speculation or release.
- **The allocation rule.** A\* is computed under the fixed allocation rule; a live mechanism sets its own budgets.
- **The prior.** The uniform prior over a reveal set is a modelling choice; priors 0.25 and 0.75 are disclosed.
- **Plan coverage.** The plan library is finite.
- **The power analysis** rests on the declared assumptions, uses normal-theory bounds, and treats the cells as fixed.
