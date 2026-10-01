# Gate 0: offline scientific feasibility (specification)

**Status.** Frozen before any candidate world was simulated. The machine-readable criteria are
`data/gate0/acceptance.json`, whose LF-normalized SHA-256 is pinned by the genesis entry of the append-only audit
`data/gate0/audit.jsonl` before the first calibration evaluation. If this document and that file disagree, the file
governs.

**Scope.**
- Gate 0 only, as specified in EXPERIMENT_0C_POSTMORTEM_AND_NEXT_DECISION.md §8 and §10.
- It makes zero API calls and runs no LLM, and it implements neither stage A nor stage B.
- It does not change frozen 0b/0c specifications, policies, prompts or results.
- It adds no new multi-agent framework and no new lifecycle primitive.
- Everything runs through the unchanged discrete-event runtime as scripted policies (`devagents/gate0/`).

**The question.** Can we construct a small, credible experimental environment in which information-dependent
organizational adaptation has measurable value over strong precommitted alternatives? This is a test of the
*testbed*, not of any model.

## 1. What counts as organizational adaptation

**The organization.** At time t, the organization O(t) is:
- the set of live agents and their parent relations;
- each agent's assignment;
- the set of agents the root is waiting on.

**Organizational adaptation.** A change to O(t) after t0: creating agents, changing the waiting set, or terminating
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
- it **improves expected net fitness** over the best precommitted alternative.

The signature counts children spawned before the reveal, children spawned after it, and children dissolved.

**Static division is not development.** A topology chosen at t0 never counts, however good it is.

## 2. The comparison classes

All classes use the same information access (any agent may read any source), the same action space, the same
execution semantics and cost accounting (the runtime), and the same resource limits. They differ only in **when an
organizational decision is fixed, and on what it may depend.**

1. **Fixed topology at t0 (F).** One plan applied to every world. It is reported, never used as a gate, because the
   router below dominates it.
2. **One-shot router (Rt).** Per cell, the best plan whose *organizational structure is fixed at t0*, chosen to
   maximize the expected fitness over the reveal set: the Bayes-optimal t0 router with a known uniform prior.
   - Its *content* may use the reveal by a fixed rule: a `triage>fan<k>` plan hands the needed documents to k
     children round-robin.
   - Its structure may not use the reveal: it cannot change k, it cannot choose between solo and divided, and it
     cannot stop waiting for a child.
   - This is the strongest possible t0 router. It knows the prior and is re-optimized at every grid point.
3. **Fixed generic workflow (W\*).** One pipeline from the W0 library, applied unchanged to every template world, and
   chosen with hindsight at each condition to maximize mean fitness over all template worlds.
   - W0 holds the generic pipelines a team would ship: blind reading, triage then solo, and triage then fan out over
     what the triage selects (fixed k, or one child per item).
   - It also holds count-contingent pipelines (fan out iff at least m items are needed), speculative fan-out over all
     candidate units, and speculation that **stops waiting for, and dissolves, units the triage rules out**.
   - W0 pipelines react to observations through fixed mechanical rules.
4. **Adaptive oracle (A\*).** The best *non-anticipating* policy over the plan library.
   - Plans are grouped by their common pre-reveal prefix. The group with the highest expected value is chosen, then
     each member gets that group's best continuation.
   - The logs verify that every plan in a group is identical before the reveal, in every member and condition.
   - A\* sees nothing a member has not revealed. It "reasons perfectly" exactly as the calibration oracle does, and
     the log must show that every needed fact reached the root before it answered (information completeness).
5. **Fully optimal contingent policy (C\*).** A theoretical reference, not a comparator. A\* ≤ C\* ≤ H\*, where H\* is
   the clairvoyant best plan per world, which ignores non-anticipation. The gap H\* − A\* is reported for every cell.

In addition:
- **No-LLM rules.** One-feature threshold rules choose between two W0 pipelines, with global thresholds. They come in
  constant, surface, workload and economic families (§5, G6).
- **W_typed.** The best W0 pipeline chosen per cell (per t0 state). It is disclosed, but it is not a gate.

### 2.1 Identifiability, and the bound on W

**Nothing here can beat C\*.** A policy with the same observations, actions and cost model cannot beat the optimal
contingent policy. In a fully specified simulator, a deterministic controller that knows the cost model and the
family's structure can implement A\*. Gate 0 therefore claims **no** advantage of "developmental intelligence" over
such a controller. The disclosures D1 and D5 report exactly how simple a controller reproduces A\*.

**What W is.** W\* is the *generic* workflow class: one precommitted pipeline for every task, with organizational
rules that use only structural observations (counts, and which units the triage selects or rules out). It is
legitimately bounded for three reasons:
- **It is what deployed harnesses are.** Plan-and-execute and map-reduce pipelines fix their organization in advance
  for a whole class of tasks.
- **A W member that computes the organization from the stated economics is no longer a fixed workflow.** It is the
  economic controller, which is A\* itself and is reported as such (D1). It is not a comparator.
- **Rules that may use workload sizes or the value of time are not excluded.** They are tested separately (G6 and
  D1), so the strength of W\* is not a hidden assumption.

**What a positive follow-up would and would not establish relative to these classes.**
- **It would establish** that a system given only general mechanisms autonomously produced economically appropriate,
  information-dependent reorganization, and captured value that no t0 topology, no generic pipeline and no surface or
  workload heuristic captures on these cells.
- **It would not establish** superiority to a cost-model controller written by someone who knows this testbed. The
  north-star claim concerns *autonomy*: the architecture is not specified by a human.

**The postmortem's §6.0 test 7.** That test says "the LLM beats a no-LLM controller running the mechanism's own rule".
It is meaningful only if that controller is the mechanism's scaffolding with a fixed default decision. If the
controller computes the economics, the test is unpassable by construction. The report states this.

## 3. The environment

**Runtime and constants.**
- Experiment 0b's frozen constants, pinned by hash in acceptance.json. The urgent value of time is 0.0016 score per
  second, and each document costs 3 s plus 0.1 s per token.
- The calibration oracle's conventions: `developmental` mode, the fixed allocation rule (`fixed_rule_spawns`), and
  oracle step pricing (estimator tokens × r input, JSON plus reasoning tokens output) at the frozen r = 2.0052 and 36
  reasoning tokens.
- Fitness is `calibrate._fitness`. Only *clean* runs count: answered, quality 1, information complete, no invalid
  action, no cap hit, no starvation, no expired lifetime.

**The plan library** (`devagents/gate0/plans.py`, generic and instantiated per member):
- `blind`;
- `triage>solo`;
- `triage>fan<k>` for k ≤ 8 and k ≤ #needed;
- `spec<k>>{wait|dissolve|cancel}`;
- `spectop<m>>{wait|dissolve|cancel}`.

Template A's speculative children triage for themselves; this is the calibration's `atstart-k`.

**No new lifecycle primitive.** Dissolution uses the runtime as it is:
- **Stopping waiting.** The root waits only for children whose units are needed. When the root answers, the runtime
  terminates every live descendant, and their in-flight charges stand.
- **Explicit cancellation.** `cancel` additionally sends a STOP MESSAGE, and a child that sees it terminates at its
  next step, returning its budget.
- **Why this is enough.** Charges are posted when an action starts, and the run ends when the root answers. So a
  parent-initiated kill primitive would add value only to work that is still to *start* while the root is still busy.
  The library prices both forms, and the report shows the value of explicit cancellation separately.

## 4. Templates and the round-1 candidate set

The parameters are in `data/gate0/candidates_round1.json`, committed in a264b17 before any simulation.

**Template A, "workload reveal".** It models a cheap investigation that reveals how much downstream work exists.
- A cheap SQL triage selects which of 14–16 candidate documents must be read.
- In member X the selected documents are the long ones (360–420 tokens). In member Y they are the tiny ones (35–40
  tokens). The count and the catalog are the same.
- After the reveal, division pays in X and is wasteful in Y.
- Instances A1–A3 cover three domains (incidents, supplier audits, client accounts).

**Template B, "dead-branch reveal".** It models a slow memo that reveals whether a long workstream is needed.
- A slow memo (950–1150 tokens, about 100–120 s to read) reveals whether the heaviest work unit (1350–1500 tokens) is
  still needed.
- In X the memo discontinues the heavy unit. In Y it names an entity that is not in the catalog, and the name has the
  same length, so both memos have one size.
- Speculative work started at t0 pays in Y. In X, the oracle dissolves the heavy unit, which is still running.
- Instances B1–B3 cover product lines, research tracks and vendor bids.

**D.** Experiment 0b's T01 (same question, same document ids), with every region report shortened to one paragraph.
It is the stage-A dissociation state, calibrated here only, and never a follow-up cell.

**Answers.** Every answer is numeric, so guessing scores about 0, except D, whose answer is one of six regions.

**Analytic expectation, recorded before evaluation (not a criterion).** The oracle's advantage over the best t0
commitment was estimated at about 0.04–0.06 for both templates: close to δ = 0.03 at unfavourable grid points.
Non-anticipation halves the value of adapting, and each child costs about 0.045 fitness (about 28 s of urgent time).
A FAIL was considered a live possibility.

## 5. Frozen acceptance criteria

δ = 0.03. A **cell** is an instance × regime, with its reveal set. The **grid** is the 18-point token grid of the 0b
calibration (`calibrate.grid` of the frozen assumptions). The **perturbations** are six single-factor changes at the
base tokens:
- document latency × 0.8 and × 1.25;
- value of time × 0.8 and × 1.25;
- all coordination fees × 2;
- message latency × 4.

| id | criterion |
|---|---|
| **G1 integrity** | Every plan is clean in every world at the base point, and every no-child plan is clean at every grid point. Every member of a reveal set has the same t0 state (system prompt and brief), the same reveal time, and identical logs before the reveal for every plan. Within a prefix group, plans have identical logs before the reveal. Members differ only in the triage source, and what it reveals differs. |
| **G2 sanity** (0b gate d) | At the base point, in every template world and in D: best fitness ≥ 0.5, and best fitness without children ≥ 0.3. |
| **G3 qualifying cell** | A template cell qualifies if, at **every** grid point: A\* − Rt ≥ δ; A\* − W\* ≥ δ; and A\*'s post-reveal signature differs between X and Y. |
| **G4 count** | At least 4 qualifying cells, from at least 2 templates with at least 2 qualifying cells each. |
| **G5 uneconomic division** | D-urgent: the best plan without children beats every plan with children by ≥ δ at every grid point. Also, at least 2 urgent template worlds needing ≥ 2 documents, from at least 2 instances, satisfy the same condition. |
| **G6 dissociation** | For every rule in the gating families (constant, surface at t0 including the conjunction "urgent ∧ ≥ m units", surface after the reveal, workload at t0, workload after the reveal), at every grid point, the rule falls ≥ δ short of A\* in at least 2 distinct cells. Rules use global thresholds at the midpoints between observed feature values, and choose between two W0 pipelines. A rule on a post-reveal feature may choose only between triage-first pipelines. |
| **G7 dissolution** | In at least 1 cell, at every grid point, A\*'s policy dissolves running work, and that is worth ≥ δ over the same prefix group's `wait` continuation. |
| **G8 robustness** | Under each perturbation, the G4 counts still hold among the G3-qualifying cells, with both advantages ≥ δ/2. |
| **G9 follow-up power** | The pre-declared follow-up (§7) fits in ≤ 400 runs and reaches joint power ≥ 0.80 under the primary assumptions. |
| **G10 audit** | The hash chain is intact, the acceptance hash matches genesis, there are ≤ 2 rounds, and every evaluation is logged. It is enforced by `begin_evaluation`; a violation aborts the evaluation. |

**Mandatory disclosures (not gates).**
- **D1:** the best economic one-line rule (value of time × workload): its shortfall, and whether it reproduces A\*.
- **D2:** W_typed against A\* in each qualifying cell.
- **D3:** H\* − A\*.
- **D4:** the attribution of A\*'s value, separating:
  - information use without reorganization (`triage>solo` − `blind`);
  - precommitted division;
  - adaptive reorganization, split into divide-or-not, choice of k, speculation, dissolution and explicit cancel.
- **D5:** whether any rule family contains a rule within δ of A\* in every cell.

### 5.1 Ambiguities resolved before evaluation, and why

- **Advantage per cell, or per member?** It is the **expectation over the reveal set**. A t0 router must make the same
  choice in both members, so it is right in one member by construction; a per-member gap would compare A\* with a
  router that has privileged knowledge. The expected gap is the decision-theoretic value of adapting organization to
  the reveal.
- **"The best fixed generic workflow".** It is **one pipeline for all template worlds**, because "generic" means not
  specialized to the task. Choosing it with hindsight at each condition makes it as strong as possible within its
  class. A per-task best pipeline (W_typed) is architecture specified by a human for that task type, so it is
  disclosed, not gated.
- **"At every grid point".** This means the 0b token grid, as in the postmortem. Environment constants are checked
  separately at δ/2, a pre-declared robustness requirement rather than a second δ test.
- **"At least two templates".** The requirement is two templates **with two qualifying cells each**, so neither
  template's result rests on a single instance.
- **"Defeats the simple rule".** The single postmortem rule is generalized to every one-feature rule in the surface and
  workload families. A defeat must occur in at least 2 cells, so that one coincidence is not enough. Economic rules
  are disclosed instead of gated, because an LLM that matched them would be doing exactly the economic reasoning under
  test.
- **"Opportunity for redirection or termination".** The dissolution must be worth ≥ δ, so that an opportunity with no
  value does not count.
- **Sanity floors.** The 0b gate (d) values are kept unchanged.

## 6. Audit rules

- **The audit file.** `data/gate0/audit.jsonl` is append-only and hash-chained (`devagents/gate0/audit.py`).
- **Genesis.** The genesis entry pins the acceptance file's and this specification's hashes. No candidate is
  evaluated before it.
- **Rounds.** A **round** is one candidate set, identified by its file hash. At most 2 rounds exist, and round 2 may be
  registered only after round 1 ends in FAIL.
- **Re-evaluation.** A round is evaluated once. It may be re-evaluated, on the same candidate set, only after a logged
  `defect` entry naming the fix commit and its regression test, at most twice. Every evaluation, including superseded
  ones, stays in the log and is reported.
- **Order of logging.** `gate0 calibrate --round N` appends `evaluation_started` before any simulation, then
  `evaluation_completed` with the results file's hash and the mechanical decision.
- **Clean code.** Evaluation refuses uncommitted changes in code, tests, specifications and acceptance files, so every
  evaluation is tied to a commit.
- **Closing a round.** `gate0 decide` closes a round and must repeat its mechanical decision. Thresholds are never
  changed after any output.
- **What cannot be enforced.**
  - Python can call the runtime directly, so an unlogged evaluation is physically possible. Enforcement is procedural,
    backed by the hash chain and the git history: the candidate file was committed (a264b17) and pushed before any
    simulation.
  - Before genesis, only *fixture* worlds were simulated: the small instances in `tests/test_gate0.py`, whose
    parameters differ from every candidate. Their results were used to test code, not to choose candidates.
- **Pre-genesis amendments** (made before any candidate evaluation, prompted by fixture tests of the power code):
  1. Control-world replication is searched over {2, 3, 4} instead of being fixed at 2. A fixed R_S = 2 made the spawn
     rate check fail in about 7% of simulations by itself.
  2. The accuracy-noninferiority interval is Agresti–Caffo instead of Wald, because Wald collapses when an arm makes no
     error.

## 7. The follow-up and its power

The follow-up is designed now and pre-registered later. No run of it is authorized.

**Cells.**
- **Information-dependent cells:** every G3-qualifying cell, with both members.
- **Controls:** the relaxed twin of each qualifying cell's instance, with both members.

**Arms.**
- **M:** the mechanism; the LLM organizes.
- **B:** per cell, the better of Rt and W\*, with a scripted organization and LLM content work.
- **N:** the no-LLM controller: the mechanism's scaffolding with a fixed default. It is modelled like B, which is
  conservative.
- **A:** the scripted oracle, 1 run per world, as an instrument check.
- **M on controls.**

**Analysis.** All of the following must pass:
- **F1, adaptation contrast:** P(X-direction reorganization | X) − P(same | Y), averaged over cells, is ≥ 0.30, and
  its two-level bootstrap lower bound is > 0.
- **F2, cost-fitness:** M − B on correct runs has a two-level bootstrap 95% lower bound > 0. Cost-fitness is fitness
  with quality fixed at 1, computed on correct runs. It is the primary comparison because a single wrong answer moves
  fitness by about 1.0, which is 20 times the organizational effect, and correctness is guarded separately by F2a.
- **F2a, accuracy:** the Agresti–Caffo lower bound of M − B is > −0.10.
- **F3, specificity:** the spawn rate on controls is ≤ 0.20.
- **F4:** F2 against N.

**Generative model** (`devagents/gate0/power.py`):
- In each run, M picks A\*'s plan with probability π_c, otherwise B's plan.
- logit π_c = logit π + s·(√ρ·z_template + √(1−ρ)·z_cell).
- Noise N(0, σ²) is added to every run.
- M's runs also carry a cell bias N(0, τ_sim²) and an organizational overhead η.
- Every run answers wrongly with probability p_fail.
- M spawns on a control world with probability s_ctl.
- The effects themselves are A\* − B per member at the base point, taken from calibration.

**Primary assumptions, declared before calibration.**

| parameter | primary value |
|---|---|
| π | 0.8 |
| s | 0.5 |
| ρ | 0.5 |
| σ | 0.05 |
| p_fail | 0.02 |
| τ_sim | 0.02 |
| η | 0.01 |
| s_ctl | 0.10 |

Justification:
- In 0c, the live B-urgent means of `single` and scripted `central` landed within 0.012 of their offline predictions,
  with no visible answer failures in 24 runs. The σ, τ_sim and p_fail values are set above what that suggests.
- π = 0.8 is the alternative of interest ("the mechanism mostly works"), not an estimate. No policy has adapted here.

**Allocation.** A fixed search over R_M, R_B = R_N and R_S, subject to ≤ 400 runs; the highest power wins.

**Reported alongside the power:**
- one-at-a-time sensitivity in π, σ, p_fail, ρ, s, τ_sim, η and s_ctl;
- a π × σ grid;
- the size of F2 under the null (M ≡ B);
- the power of the postmortem's raw-fitness version of F2;
- API calls, list-price spend and wall time, for a presentation mechanism and a deliberation mechanism (2 checkpoints
  per run, each with 2,000 extra output tokens and 40 s of wall time; 8 s of wall time per ordinary call).

**What the power is not.** It is conditional on declared assumptions, never empirically established.

## 8. Decision

- **INDETERMINATE** if G1 fails or the evaluation cannot complete. The report then states what remains unresolved and
  what resolving it would cost.
- **PASS** if G1–G10 all hold.
- **FAIL** otherwise.

**Rounds.** Round 2 may follow a round-1 FAIL, with a revised candidate set justified by the diagnosed failure and
logged before evaluation. The criteria never change. A round-2 FAIL is final.

**What each outcome authorizes.**
- **PASS** authorizes only a review of Gate 0. It does not authorize stage A.
- **FAIL** closes this formulation of the research program under the postmortem's stopping rule (§10, rule 4): the
  north-star line stops in this simulator.

## 9. Known limitations, stated in advance

- **The oracle's perfect reasoning.** Only the information is checked; content work is assumed correct.
- **The latency constants.** The declared LLM latency and per-document latency are assumptions validated live only for
  0c's t0 fan-out, not for speculation or dissolution.
- **The prior.** The uniform prior over a reveal set is a modelling choice.
- **Plan coverage.** The plan library is finite. H\* bounds what it misses only within the library.
- **The power analysis** rests on the declared assumptions above, and on a bootstrap approximation that resamples
  cells exactly and runs within a cell by normal draws.
